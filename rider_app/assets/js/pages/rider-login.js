let isOtpSent = false;
const form = document.getElementById('rider-login-form');
const btn = document.getElementById('action-btn');
const msg = document.getElementById('error-msg');

if(localStorage.getItem(RIDER_CONFIG.STORAGE_KEYS.TOKEN)) {
    window.location.href = RIDER_CONFIG.ROUTES.DASHBOARD;
}

form.addEventListener('submit', async (e) => {
    e.preventDefault();
    const phone = document.getElementById('phone').value;
    const otp = document.getElementById('otp').value;
    msg.innerText = "";

    try {
        btn.disabled = true;
        btn.innerText = "Processing...";

        if (!isOtpSent) {
            const res = await ApiService.post('/notifications/send-otp/', { phone });
            isOtpSent = true;
            document.getElementById('otp-group').style.display = 'flex';
            document.getElementById('phone').disabled = true;
            btn.innerText = "Verify & Login";
            
            // 🔥 Yahan OTP Toast message mein show karega
            const demoOtp = res.otp || '123456'; 
            
            if(window.showToast) {
                window.showToast(`TEST MODE: Your OTP is ${demoOtp}`, 'success');
            } else {
                alert(`OTP Sent: ${demoOtp}`); // Fallback agar css/js miss ho
            }
            
            // User ki suvidha ke liye field me direct fill kar dete hain
            document.getElementById('otp').value = demoOtp; 

        } else {
            if(!otp) throw { message: "Please enter OTP" };
            const res = await ApiService.post('/auth/register/customer/', { phone, otp });
            localStorage.setItem(RIDER_CONFIG.STORAGE_KEYS.TOKEN, res.access);
            
            try {
                // Verify Rider Role
                await ApiService.get('/riders/me/');
                if(window.showToast) window.showToast("Login Successful!", 'success');
                
                setTimeout(() => {
                    window.location.href = RIDER_CONFIG.ROUTES.DASHBOARD;
                }, 1000);
            } catch(err) {
                msg.innerText = "Access Denied: Not a Rider Account";
                localStorage.clear();
            }
        }
    } catch (err) {
        msg.innerText = err.message || "Something went wrong";
        if(window.showToast) window.showToast(err.message || "An error occurred", 'error');
        if(isOtpSent) btn.innerText = "Verify & Login";
        else btn.innerText = "Get OTP";
    } finally {
        btn.disabled = false;
    }
});