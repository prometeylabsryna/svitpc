(() => {
  const form = document.querySelector('form[data-autosubmit]');
  if (!form) return;
  // Small delay to let the spinner render before navigation
  setTimeout(() => form.submit(), 400);
})();
