// Wire up the button and the nav link.
const button = document.querySelector('.btn');
button.addEventListener('click', () => {
  document.querySelector('.nav-link').classList.add('active');
});
