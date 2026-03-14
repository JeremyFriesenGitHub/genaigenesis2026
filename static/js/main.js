// Scroll reveal via Intersection Observer
const observer = new IntersectionObserver(
  (entries) => {
    entries.forEach((entry) => {
      if (entry.isIntersecting) {
        entry.target.classList.add('visible');
      }
    });
  },
  { threshold: 0.1, rootMargin: '0px 0px -40px 0px' }
);

document.querySelectorAll('.reveal').forEach((el) => observer.observe(el));

// Navbar glass effect on scroll
const navbar = document.getElementById('navbar');
window.addEventListener(
  'scroll',
  () => {
    navbar.classList.toggle('nav-scrolled', window.scrollY > 50);
  },
  { passive: true }
);
