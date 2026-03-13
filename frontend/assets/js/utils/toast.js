/* assets/js/utils/toast.js */
window.Toast = {
    timeout1: null,
    timeout2: null,

    // Naya Dynamic Island Toast Logic
    show: function(message, type = 'info', duration = 3000) {
        let island = document.getElementById('dynamic-island-toast');
        
        // Agar island container nahi hai toh banayein
        if (!island) {
            island = document.createElement('div');
            island.id = 'dynamic-island-toast';
            island.className = 'dynamic-island';
            
            island.innerHTML = `
                <div class="island-icon" id="island-icon">🔔</div>
                <div class="island-text">
                    <div class="island-title" id="island-title">Notification</div>
                    <div class="island-message" id="island-message"></div>
                </div>
            `;
            document.body.appendChild(island);
        }

        const iconEl = document.getElementById('island-icon');
        const titleEl = document.getElementById('island-title');
        const messageEl = document.getElementById('island-message');

        // Message set karein (Security ke liye innerText use kiya hai)
        messageEl.innerText = message;

        // Type ke hisaab se styling aur title set karein
        let bgColor, icon, title;
        switch(type) {
            case 'success':
                bgColor = '#2ecc71';
                icon = '✅';
                title = 'Success';
                break;
            case 'error':
                bgColor = '#e74c3c';
                icon = '❌';
                title = 'Error';
                break;
            case 'warning':
                bgColor = '#f1c40f';
                icon = '⚠️';
                title = 'Warning';
                break;
            default:
                bgColor = '#3498db';
                icon = '🔔';
                title = 'Info';
        }

        iconEl.style.background = bgColor;
        iconEl.innerHTML = icon;
        titleEl.innerText = title;

        // Purani animation clear karein
        island.classList.remove('show', 'expand');
        void island.offsetWidth; // Reflow trigger karne ke liye taaki animation smoothly dobara chale
        
        // Show island
        island.classList.add('show');
        
        // Thodi der mein text area expand karein
        setTimeout(() => {
            island.classList.add('expand');
        }, 200);

        // Naya timeout set karne se pehle purana clear karein (agar multiple click ho toh overlap na ho)
        if (this.timeout1) clearTimeout(this.timeout1);
        if (this.timeout2) clearTimeout(this.timeout2);
        
        // Duration (default 3000ms) ke baad gayab karein
        this.timeout1 = setTimeout(() => {
            island.classList.remove('expand');
            this.timeout2 = setTimeout(() => {
                island.classList.remove('show');
            }, 300); 
        }, duration); 
    },

    // ==========================================
    // Dev OTP Logic (Exactly jaisa aapne diya tha, koi change nahi)
    // ==========================================
    devOTP: function(otp) {
        let container = document.getElementById('dev-toast-container');
        if (!container) {
            container = document.createElement('div');
            container.id = 'dev-toast-container';
            
            // --- NAYA FIX: OTP Container ko screen ke center mein laane ke liye ---
            container.style.position = 'fixed';
            container.style.top = '40%'; // Screen par upar se 40% niche
            container.style.left = '50%';
            container.style.transform = 'translate(-50%, -50%)';
            container.style.zIndex = '99999'; // Sabse upar dikhne ke liye
            container.style.width = '90%'; // Mobile screen ke hisaab se
            container.style.maxWidth = '400px';
            container.style.display = 'flex';
            container.style.flexDirection = 'column';
            container.style.alignItems = 'center';
            // ---------------------------------------------------------------------
            
            document.body.appendChild(container);
        }

        const toast = document.createElement('div');
        toast.className = 'toast toast-dev show'; // 'show' class तुरंत जोड़ें
        
        // --- NAYA FIX: Toast ki thodi designing taaki center me achha lage ---
        toast.style.pointerEvents = "auto";
        toast.style.width = "100%";
        toast.style.boxShadow = "0 10px 25px rgba(0,0,0,0.2)"; // Thoda shadow jisse pop-up jaisa lage
        toast.style.border = "2px solid #7209b7";
        toast.style.backgroundColor = "#fff"; // Default background incase CSS is missing
        toast.style.padding = "16px";
        toast.style.borderRadius = "12px";
        toast.style.display = "flex";
        toast.style.justifyContent = "space-between";
        toast.style.alignItems = "center";
        // ---------------------------------------------------------------------

        const content = document.createElement('div');
        content.className = 'toast-content';
        content.style.display = 'flex';
        content.style.alignItems = 'center';
        content.style.gap = '12px';

        // Icon
        const iconWrap = document.createElement('span');
        iconWrap.className = 'toast-icon';
        iconWrap.innerHTML = '<i class="fas fa-tools" style="color: #7209b7; font-size: 1.5rem;"></i>';

        // Message HTML
        const msgWrap = document.createElement('div');
        msgWrap.className = 'toast-msg';
        msgWrap.style.display = 'flex';
        msgWrap.style.flexDirection = 'column';
        msgWrap.innerHTML = `
            <span style="font-weight:bold; color:#555; font-size:0.9rem;">SMS Service Unavailable</span>
            <span style="margin-top:4px; font-size: 0.95rem; color: #333;">
                Use Temporary OTP: 
                <b style="background:#7209b7; color:#fff; padding:2px 6px; border-radius:4px; letter-spacing:1px; font-size: 1.1rem;">${otp}</b>
            </span>
        `;

        // Close Button
        const closeBtn = document.createElement('button');
        closeBtn.className = 'toast-close';
        closeBtn.innerHTML = '&times;';
        closeBtn.style.background = 'transparent';
        closeBtn.style.border = 'none';
        closeBtn.style.fontSize = '1.5rem';
        closeBtn.style.color = '#aaa';
        closeBtn.style.cursor = 'pointer';
        closeBtn.onclick = () => toast.remove();

        content.appendChild(iconWrap);
        content.appendChild(msgWrap);
        toast.appendChild(content);
        toast.appendChild(closeBtn);
        container.appendChild(toast);

        // 20 सेकंड का टाइमर (20000 ms)
        setTimeout(() => {
            toast.style.opacity = '0';
            toast.style.transition = 'opacity 0.3s ease';
            setTimeout(() => toast.remove(), 300);
        }, 20000);
    },

    // Shortcuts for standard notifications
    success: function(msg) { this.show(msg, 'success'); },
    error: function(msg) { this.show(msg, 'error'); },
    warning: function(msg) { this.show(msg, 'warning'); },
    info: function(msg) { this.show(msg, 'info'); }
};