let isOtpSent = false;
const form = document.getElementById('rider-login-form');
const btn = document.getElementById('action-btn');
const msg = document.getElementById('error-msg');

// Agar pehle se login hai toh dashboard par bhej do
if(localStorage.getItem(RIDER_CONFIG.STORAGE_KEYS.TOKEN)) {
    window.location.href = RIDER_CONFIG.ROUTES.DASHBOARD;
}

form.addEventListener('submit', async (e) => {
    e.preventDefault();
    const phone = document.getElementById('phone').value.trim();
    const otp = document.getElementById('otp').value.trim();
    msg.innerText = "";

    try {
        btn.disabled = true;
        btn.innerText = "Processing...";

        if (!isOtpSent) {
            // STEP 1: SEND OTP
            const res = await ApiService.post('/notifications/send-otp/', { phone });
            isOtpSent = true;
            
            document.getElementById('otp-group').style.display = 'flex';
            document.getElementById('phone').disabled = true;
            btn.innerText = "Verify & Login";
            
            // 🔥 OTP nikalna aur show karna
            const demoOtp = res.otp || '123456'; 
            
            if (typeof window.showToast === 'function') {
                window.showToast(`Test Mode: Your OTP is ${demoOtp}`, 'success');
            } else {
                alert(`Test Mode: Your OTP is ${demoOtp}`);
            }
            
            // Suvidha ke liye form auto-fill
            document.getElementById('otp').value = demoOtp; 

        } else {
            // STEP 2: VERIFY OTP
            if(!otp) {
                if (typeof window.showToast === 'function') window.showToast("Please enter OTP", 'error');
                throw { message: "Please enter OTP" };
            }
            
            const res = await ApiService.post('/auth/register/customer/', { phone, otp });
            localStorage.setItem(RIDER_CONFIG.STORAGE_KEYS.TOKEN, res.access);
            
            try {
                // Verify ki ye sach me rider account hai
                await ApiService.get('/riders/me/');
                if (typeof window.showToast === 'function') window.showToast("Login Successful!", 'success');
                
                setTimeout(() => {
                    window.location.href = RIDER_CONFIG.ROUTES.DASHBOARD;
                }, 1000);
                
            } catch(err) {
                msg.innerText = "Access Denied: Not a Rider Account";
                localStorage.removeItem(RIDER_CONFIG.STORAGE_KEYS.TOKEN);
                isOtpSent = false; // Reset form
                document.getElementById('otp-group').style.display = 'none';
                document.getElementById('phone').disabled = false;
            }
        }
    } catch (err) {
        let errorText = err.message || "Something went wrong";
        // Agar backend se direct message aa raha hai array form me
        if (err.error && err.error.message) {
            errorText = err.error.message;
        }
        
        msg.innerText = errorText;
        if (typeof window.showToast === 'function') window.showToast(errorText, 'error');
        
    } finally {
        btn.disabled = false;
        if(isOtpSent) btn.innerText = "Verify & Login";
        else btn.innerText = "Get OTP";
    }
});