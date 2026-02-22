// assets/js/pages/auth.js

const stepPhone = document.getElementById('step-phone');
const stepOtp = document.getElementById('step-otp');
let phoneNumber = '';

document.addEventListener('DOMContentLoaded', () => {
    if (localStorage.getItem(APP_CONFIG.STORAGE_KEYS.TOKEN)) {
        window.location.href = APP_CONFIG.ROUTES.HOME;
        return;
    }
    
    const phoneForm = document.getElementById('step-phone');
    if (phoneForm) phoneForm.addEventListener('submit', handleSendOtp);
    
    const otpForm = document.getElementById('step-otp');
    if (otpForm) otpForm.addEventListener('submit', handleVerifyAndLogin);

    // 🔥 NEW: Advanced & Smooth OTP Input Logic
    const otpInputs = document.querySelectorAll('.otp-input');
    otpInputs.forEach((input, index) => {
        // Typing handler
        input.addEventListener('input', (e) => {
            input.value = input.value.replace(/[^0-9]/g, ''); // Sirf numbers allow
            if (input.value && index < otpInputs.length - 1) {
                otpInputs[index + 1].focus(); // Next box me jao
            }
        });

        // Backspace (Delete) handler
        input.addEventListener('keydown', (e) => {
            if (e.key === 'Backspace' && !input.value && index > 0) {
                otpInputs[index - 1].focus(); // Pichle box me jao
            }
        });

        // Copy-Paste handler
        input.addEventListener('paste', (e) => {
            e.preventDefault();
            const pasteData = e.clipboardData.getData('text').replace(/[^0-9]/g, '').slice(0, 6);
            pasteData.split('').forEach((char, i) => {
                if (otpInputs[i]) {
                    otpInputs[i].value = char;
                    if (i < 5) otpInputs[i + 1].focus();
                }
            });
        });
    });
});

async function handleSendOtp(e) {
    e.preventDefault();
    const rawInput = document.getElementById('phone-input').value.replace(/\D/g, '');
    
    if (!/^[6-9]\d{9}$/.test(rawInput) || rawInput.length !== 10) {
        return Toast.error("Please enter a valid 10-digit mobile number");
    }

    const btn = document.getElementById('get-otp-btn');
    const originalHtml = btn.innerHTML;
    btn.disabled = true;
    btn.innerHTML = 'Sending...';

    try {
        phoneNumber = `+91${rawInput}`;
        
        const res = await ApiService.post('/notifications/send-otp/', { phone: phoneNumber });
        
        stepPhone.style.display = 'none';
        stepOtp.style.display = 'block';
        document.getElementById('display-phone').innerText = phoneNumber;
        
        if (res.debug_otp) {
            Toast.devOTP(res.debug_otp); 
            
            // 🔥 NEW: Dev mode mein automatically 6 boxes fill ho jayenge!
            const debugOtpStr = String(res.debug_otp);
            const otpInputs = document.querySelectorAll('.otp-input');
            otpInputs.forEach((inp, i) => {
                if (debugOtpStr[i]) inp.value = debugOtpStr[i];
            });

        } else {
            Toast.success("OTP Sent successfully");
        }

        startTimerLocal();
        
        setTimeout(() => {
            const firstInput = document.querySelector('.otp-input');
            if(firstInput) firstInput.focus();
        }, 100);

    } catch (err) { 
        console.error(err);
        Toast.error(err.message || "Failed to send OTP"); 
    } finally {
        btn.innerHTML = originalHtml;
        btn.disabled = false;
    }
}

async function handleVerifyAndLogin(e) {
    e.preventDefault();
    let otp = '';
    document.querySelectorAll('.otp-input').forEach(i => otp += i.value);
    
    if(otp.length !== 6) return Toast.warning("Please enter complete 6-digit OTP");

    const btn = document.getElementById('verify-btn');
    const originalText = btn.innerText;
    btn.disabled = true;
    btn.innerText = "Verifying...";
    
    try {
        const res = await ApiService.post('/auth/register/customer/', { 
            phone: phoneNumber, 
            otp: otp 
        });

        if (res.access) {
            localStorage.setItem(APP_CONFIG.STORAGE_KEYS.TOKEN, res.access);
            if(res.refresh) localStorage.setItem(APP_CONFIG.STORAGE_KEYS.REFRESH, res.refresh);
            
            try {
                const user = await ApiService.get('/auth/me/');
                localStorage.setItem(APP_CONFIG.STORAGE_KEYS.USER, JSON.stringify(user));
            } catch(e) { console.warn("Profile fetch failed", e); }
            
            Toast.success("Login Successful");
                ApiService.clearCache();
            window.location.href = APP_CONFIG.ROUTES.HOME;
        } else {
            throw new Error("No access token received");
        }

    } catch (err) {
        console.error(err);
        Toast.error(err.message || "Verification Failed");
        btn.disabled = false;
        btn.innerText = originalText;
    }
}

function startTimerLocal() {
    let time = 30;
    const el = document.getElementById('timer');
    if(!el) return;
    const interval = setInterval(() => {
        el.innerText = --time;
        if(time <= 0) clearInterval(interval);
    }, 1000);
}

window.resetForm = function() {
    stepOtp.style.display = 'none';
    stepPhone.style.display = 'block';
    document.getElementById('get-otp-btn').disabled = false;
    // OTP boxes clear kar do jab form reset ho
    document.querySelectorAll('.otp-input').forEach(i => i.value = '');
}