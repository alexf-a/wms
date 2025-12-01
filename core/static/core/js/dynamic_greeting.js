(function() {
    const greetings = [
        "Welcome to WMS",
        "Find Your Shi...Stuff",
        "Storage, Simplified",
        "Where's My...? Solved",
        "Chaos → Order"
    ];
    
    const el = document.getElementById('dynamic-welcome');
    if (!el) return;
    
    // Pick a random greeting on load
    el.textContent = greetings[Math.floor(Math.random() * greetings.length)];
    
    // Rotate greetings every 3 seconds with fade
    let index = greetings.indexOf(el.textContent);
    setInterval(() => {
        el.style.opacity = '0';
        setTimeout(() => {
            index = (index + 1) % greetings.length;
            el.textContent = greetings[index];
            el.style.opacity = '1';
        }, 300);
    }, 2000);
})();
