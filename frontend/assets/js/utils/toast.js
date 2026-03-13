/* assets/js/utils/toast.js */
(function() {
    const Toast = {
        timeout1: null,
        timeout2: null,

        init() {
            // Agar pehle se island exist karta hai, toh waise hi rehne do
            if (document.getElementById('dynamic-island-toast')) return;
            
            const island = document.createElement('div');
            island.id = 'dynamic-island-toast';
            island.className = 'dynamic-island';
            
            island.innerHTML = `
                <div class="island-icon" id="island-icon">🔔</div>
                <div class="island-text">
                    <div class="island-title" id="island-title">Notification</div>
                    <div class="island-message" id="island-message">Message</div>
                </div>
            `;
            
            document.body.appendChild(island);
        },

        show(title, message, type = 'info') {
            this.init(); // DOM injection check
            
            const island = document.getElementById('dynamic-island-toast');
            const iconEl = document.getElementById('island-icon');
            const titleEl = document.getElementById('island-title');
            const messageEl = document.getElementById('island-message');

            // Text Set Karein
            titleEl.textContent = title || 'Notification';
            messageEl.textContent = message || '';

            // Type ke hisaab se color aur icon change karein
            let bgColor, icon;
            switch(type) {
                case 'success':
                    bgColor = '#2ecc71'; // Green theme color
                    icon = '✅'; // Aap yaha FontAwesome icons bhi use kar sakte ho jaise '<i class="fas fa-check"></i>'
                    break;
                case 'error':
                    bgColor = '#e74c3c'; // Red
                    icon = '❌';
                    break;
                case 'warning':
                    bgColor = '#f1c40f'; // Yellow
                    icon = '⚠️';
                    break;
                default:
                    bgColor = '#3498db'; // Blue
                    icon = '🔔';
            }

            iconEl.style.background = bgColor;
            iconEl.innerHTML = icon;

            // Purani animations hatayein
            island.classList.remove('show', 'expand');
            
            // Reflow trigger karein animation restart karne ke liye
            void island.offsetWidth;
            
            // Island dikhayein
            island.classList.add('show');
            
            // Thodi der baad text expand karein
            setTimeout(() => {
                island.classList.add('expand');
            }, 200);

            // Purane timeout clear karein agar naya message aa gaya
            if (this.timeout1) clearTimeout(this.timeout1);
            if (this.timeout2) clearTimeout(this.timeout2);
            
            // Message ko 3-4 second baad wapas hide kar dein
            this.timeout1 = setTimeout(() => {
                island.classList.remove('expand'); // Pehle shrink karo
                this.timeout2 = setTimeout(() => {
                    island.classList.remove('show'); // Phir gayab karo
                }, 300); 
            }, 3500); 
        },

        // Project ke existing methods jisse baaki code break na ho
        success(message, title = 'Success') {
            this.show(title, message, 'success');
        },

        error(message, title = 'Error') {
            this.show(title, message, 'error');
        },

        info(message, title = 'Info') {
            this.show(title, message, 'info');
        },

        warning(message, title = 'Warning') {
            this.show(title, message, 'warning');
        }
    };

    window.Toast = Toast;
})();