window.Toast = {
    show: function(message, type = 'info', duration = 3000) {
        let container = document.getElementById('toast-container');
        if (!container) {
            container = document.createElement('div');
            container.id = 'toast-container';
            document.body.appendChild(container);
        }

        const toast = document.createElement('div');
        toast.className = `toast toast-${type}`;
        
        const icons = {
            success: 'fa-check-circle',
            error: 'fa-exclamation-circle',
            warning: 'fa-exclamation-triangle',
            info: 'fa-info-circle'
        };

        // UI Structure
        const content = document.createElement('div');
        content.className = 'toast-content';

        const iconWrap = document.createElement('span');
        iconWrap.className = 'toast-icon';
        iconWrap.innerHTML = `<i class="fas ${icons[type] || icons.info}"></i>`;

        const msgWrap = document.createElement('span');
        msgWrap.className = 'toast-msg';
        msgWrap.innerText = message; // SECURITY FIX: Use innerText instead of innerHTML

        const closeBtn = document.createElement('button');
        closeBtn.className = 'toast-close';
        closeBtn.innerHTML = '&times;';
        closeBtn.onclick = () => toast.remove();

        content.appendChild(iconWrap);
        content.appendChild(msgWrap);
        toast.appendChild(content);
        toast.appendChild(closeBtn);
        container.appendChild(toast);

        setTimeout(() => toast.classList.add('show'), 10);
        setTimeout(() => {
            toast.classList.remove('show');
            setTimeout(() => toast.remove(), 300);
        }, duration);
    },

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
        // ---------------------------------------------------------------------

        const content = document.createElement('div');
        content.className = 'toast-content';

        // Icon
        const iconWrap = document.createElement('span');
        iconWrap.className = 'toast-icon';
        iconWrap.innerHTML = '<i class="fas fa-tools"></i>';

        // Message HTML
        const msgWrap = document.createElement('div');
        msgWrap.className = 'toast-msg';
        msgWrap.style.display = 'flex';
        msgWrap.style.flexDirection = 'column';
        msgWrap.innerHTML = `
            <span style="font-weight:bold; color:#555; font-size:0.9rem;">SMS Service Unavailable</span>
            <span style="margin-top:4px;">
                Use Temporary OTP: 
                <b style="background:#7209b7; color:#fff; padding:2px 6px; border-radius:4px; letter-spacing:1px; font-size: 1.1rem;">${otp}</b>
            </span>
        `;

        // Close Button
        const closeBtn = document.createElement('button');
        closeBtn.className = 'toast-close';
        closeBtn.innerHTML = '&times;';
        closeBtn.onclick = () => toast.remove();

        content.appendChild(iconWrap);
        content.appendChild(msgWrap);
        toast.appendChild(content);
        toast.appendChild(closeBtn);
        container.appendChild(toast);

        // 20 सेकंड का टाइमर (20000 ms)
        setTimeout(() => {
            toast.style.opacity = '0';
            setTimeout(() => toast.remove(), 300);
        }, 20000);
    },

    success: function(msg) { this.show(msg, 'success'); },
    error: function(msg) { this.show(msg, 'error'); },
    warning: function(msg) { this.show(msg, 'warning'); },
    info: function(msg) { this.show(msg, 'info'); }
};