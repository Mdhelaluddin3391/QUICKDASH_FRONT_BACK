let isOtpSent = false;
const form = document.getElementById('rider-login-form');
const btn = document.getElementById('action-btn');
const msg = document.getElementById('error-msg');

if(localStorage.getItem(window.RIDER_CONFIG.STORAGE_KEYS.TOKEN)) {
    window.location.href = window.RIDER_CONFIG.ROUTES.DASHBOARD;
}

form.addEventListener('submit', async (e) => {
    e.preventDefault();
    
    // UPDATED: Sirf number extract karna (spaces/symbols hatana)
    let rawPhone = document.getElementById('phone').value.replace(/\D/g, ''); 
    const otp = document.getElementById('otp').value.trim();
    msg.innerText = "";

    // Strictly 10 digit ka number hona chahiye
    if (rawPhone.length !== 10) {
        msg.innerText = "Please enter a valid 10-digit phone number.";
        if (typeof window.showToast === 'function') window.showToast("Invalid number", 'error');
        return;
    }

    // Backend ko specifically format pass karna
    let formattedPhone = `+91${rawPhone}`;

    try {
        btn.disabled = true;
        btn.innerText = "Processing...";

        if (!isOtpSent) {
            // Send OTP
            const res = await ApiService.post('/notifications/send-otp/', { 
                phone: formattedPhone
            });
            isOtpSent = true;
            
            document.getElementById('otp-group').style.display = 'flex';
            document.getElementById('phone').disabled = true;
            btn.innerText = "Verify & Login";
            
            // Backend ki `debug_otp` field se real OTP nikalna 
            const realOtp = res.debug_otp; 
            
            // Ek custom bada Alert/Toast banate hain jo center mein dikhe aur lamba ruke (15 seconds)
            let toastContainer = document.getElementById('dev-toast-container');
            if (!toastContainer) {
                toastContainer = document.createElement('div');
                toastContainer.id = 'dev-toast-container';
                document.body.appendChild(toastContainer);
            }

            toastContainer.innerHTML = `
                <div class="center-otp-toast">
                    <span style="font-size: 0.9rem; color: #555;">Dev Mode / SMS Blocked</span><br/>
                    <b style="font-size: 1.5rem; color: var(--primary); letter-spacing: 2px;">OTP: ${realOtp}</b>
                </div>
            `;

            // 15 Second (15000ms) baad toast ko hata dena
            setTimeout(() => {
                toastContainer.innerHTML = '';
            }, 15000);
            
            // Rider ko type nahi karna padega, auto-fill kar dete hain
            document.getElementById('otp').value = realOtp; 

        } else {
            // Verify
            if(!otp) {
                if (typeof window.showToast === 'function') window.showToast("Please enter OTP", 'error');
                throw { message: "Please enter OTP" };
            }
            
            const res = await ApiService.post('/accounts/register/customer/', { phone: formattedPhone, otp });
            localStorage.setItem(window.RIDER_CONFIG.STORAGE_KEYS.TOKEN, res.access);
            
            try {
                await ApiService.get('/riders/me/');
                if (typeof window.showToast === 'function') window.showToast("Login Successful!", 'success');
                
                setTimeout(() => {
                    window.location.href = window.RIDER_CONFIG.ROUTES.DASHBOARD;
                }, 1000);
            } catch(err) {
                msg.innerText = "Access Denied: Not a Rider Account";
                localStorage.removeItem(window.RIDER_CONFIG.STORAGE_KEYS.TOKEN);
                isOtpSent = false; 
                document.getElementById('otp-group').style.display = 'none';
                document.getElementById('phone').disabled = false;
            }
        }
    } catch (err) {
        console.error("Full Error Details:", err);
        
        // Better Error Message Display
        let errorText = "Something went wrong";
        
        if (err.message) {
            if (typeof err.message === 'string') {
                errorText = err.message;
            } else if (typeof err.message === 'object') {
                // Agar error array/object form me hai (jaise {phone: ["Invalid number"]})
                errorText = Object.values(err.message).flat().join(' | ');
            }
        }

        msg.innerText = errorText;
        if (typeof window.showToast === 'function') window.showToast(errorText, 'error');
        
    } finally {
        btn.disabled = false;
        if(isOtpSent) btn.innerText = "Verify & Login";
        else btn.innerText = "Get OTP";
    }
});

// Redirect to dashboard if already logged in on page load
document.addEventListener('DOMContentLoaded', () => {
    if(localStorage.getItem(window.RIDER_CONFIG.STORAGE_KEYS.TOKEN)) {
        window.location.href = window.RIDER_CONFIG.ROUTES.DASHBOARD;
    }
});