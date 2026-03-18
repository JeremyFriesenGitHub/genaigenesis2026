import boto3
import logging
import os
import time

logger = logging.getLogger(__name__)

NOTEBOOK_NAME = os.environ.get("SAGEMAKER_NOTEBOOK_NAME", "personaplex-gpu")
AWS_REGION = os.environ.get("SAGEMAKER_REGION", "ca-central-1")

_sm = None
_ec2 = None


def _sm_client():
    global _sm
    if _sm is None:
        _sm = boto3.client("sagemaker", region_name=AWS_REGION)
    return _sm


def _ec2_client():
    global _ec2
    if _ec2 is None:
        _ec2 = boto3.client("ec2", region_name=AWS_REGION)
    return _ec2


def _get_notebook_ec2_ip() -> str:
    """Find the public IP of the EC2 instance backing the SageMaker notebook."""
    resp = _ec2_client().describe_instances(
        Filters=[
            {"Name": "tag:aws:sagemaker:notebook-instance-name", "Values": [NOTEBOOK_NAME]},
            {"Name": "instance-state-name", "Values": ["running"]},
        ]
    )
    for reservation in resp.get("Reservations", []):
        for inst in reservation.get("Instances", []):
            ip = inst.get("PublicIpAddress", "")
            if ip:
                return ip
    raise RuntimeError(f"No running EC2 found for notebook {NOTEBOOK_NAME}")


def start_notebook(poll_interval: float = 10.0, timeout: float = 300.0) -> str:
    """Start SageMaker notebook, wait until InService, return public IP."""
    sm = _sm_client()
    sm.start_notebook_instance(NotebookInstanceName=NOTEBOOK_NAME)
    logger.info("Starting SageMaker notebook %s", NOTEBOOK_NAME)

    deadline = time.time() + timeout
    while time.time() < deadline:
        time.sleep(poll_interval)
        resp = sm.describe_notebook_instance(NotebookInstanceName=NOTEBOOK_NAME)
        status = resp["NotebookInstanceStatus"]
        logger.debug("Notebook status: %s", status)
        if status == "InService":
            ip = _get_notebook_ec2_ip()
            logger.info("Notebook InService, IP=%s", ip)
            return ip
        if status in ("Failed", "Deleting"):
            raise RuntimeError(f"Notebook entered unexpected state: {status}")

    raise TimeoutError(f"Notebook did not reach InService within {timeout}s")


def stop_notebook() -> None:
    """Stop SageMaker notebook to save costs."""
    _sm_client().stop_notebook_instance(NotebookInstanceName=NOTEBOOK_NAME)
    logger.info("Stopped SageMaker notebook %s", NOTEBOOK_NAME)
