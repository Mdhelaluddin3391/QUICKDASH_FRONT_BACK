let isOtpSent = false;
const form = document.getElementById('rider-login-form');
const btn = document.getElementById('action-btn');
const msg = document.getElementById('error-msg');

if(localStorage.getItem(RIDER_CONFIG.STORAGE_KEYS.TOKEN)) {
    window.location.href = RIDER_CONFIG.ROUTES.DASHBOARD;
}

form.addEventListener('submit', async (e) => {
    e.preventDefault();
    let phone = document.getElementById('phone').value.trim();
    const otp = document.getElementById('otp').value.trim();
    msg.innerText = "";

    // 🔥 FIX 1: Auto Format Phone Number (Agar user +91 bhool jaye)
    if (!phone.startsWith('+')) {
        if (phone.length === 10) {
            phone = '+91' + phone; // India ka code default add karo
        } else {
            phone = '+' + phone;
        }
    }

    try {
        btn.disabled = true;
        btn.innerText = "Processing...";

        if (!isOtpSent) {
            // Send OTP
            const res = await ApiService.post('/notifications/send-otp/', { 
                phone: phone,          // Backend ko check karein agar ye 'phone_number' chahiye toh isko phone_number: phone kardein
                phone_number: phone    // Safe side dono bhej dete hain taaki ek toh catch ho hi jaye
            });
            isOtpSent = true;
            
            document.getElementById('otp-group').style.display = 'flex';
            document.getElementById('phone').disabled = true;
            btn.innerText = "Verify & Login";
            
            // 🔥 FIX: Backend ki `debug_otp` field se real OTP nikalna 
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
            
            const res = await ApiService.post('/auth/register/customer/', { phone: phone, phone_number: phone, otp });
            localStorage.setItem(RIDER_CONFIG.STORAGE_KEYS.TOKEN, res.access);
            
            try {
                await ApiService.get('/riders/me/');
                if (typeof window.showToast === 'function') window.showToast("Login Successful!", 'success');
                
                setTimeout(() => {
                    window.location.href = RIDER_CONFIG.ROUTES.DASHBOARD;
                }, 1000);
            } catch(err) {
                msg.innerText = "Access Denied: Not a Rider Account";
                localStorage.removeItem(RIDER_CONFIG.STORAGE_KEYS.TOKEN);
                isOtpSent = false; 
                document.getElementById('otp-group').style.display = 'none';
                document.getElementById('phone').disabled = false;
            }
        }
    } catch (err) {
        console.error("Full Error Details:", err);
        
        // 🔥 FIX 2: Better Error Message Display
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