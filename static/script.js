document.addEventListener('DOMContentLoaded', function() {
    // Get the progress bar element and its width from the backend (Flask)
    const progress = document.querySelector('.progress');
    const healthScore = parseFloat(progress.style.width); // Getting the width of progress bar from style

    // Optional: animate the health score visualization (for smooth transition)
    let currentWidth = 0;
    const interval = setInterval(() => {
        if (currentWidth < healthScore) {
            currentWidth++;
            progress.style.width = currentWidth + '%';
            progress.textContent = currentWidth + '%'; // Optional: display percentage in progress bar
        } else {
            clearInterval(interval);
        }
    }, 10);
});
