// assets/js/pages/auth.js

let isUsingFirebase = false; 
let confirmationResult = null;
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

    // 🔥 Advanced & Smooth OTP Input Logic
    const otpInputs = document.querySelectorAll('.otp-input');
    otpInputs.forEach((input, index) => {
        input.addEventListener('input', (e) => {
            input.value = input.value.replace(/[^0-9]/g, ''); 
            if (input.value && index < otpInputs.length - 1) {
                otpInputs[index + 1].focus(); 
            }
        });

        input.addEventListener('keydown', (e) => {
            if (e.key === 'Backspace' && !input.value && index > 0) {
                otpInputs[index - 1].focus(); 
            }
        });

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

    phoneNumber = `+91${rawInput}`;

    try {
        // 🔥 PLAN A: Firebase SMS Attempt (Fixed for Compat API)
        if (!window.recaptchaVerifier) {
            window.recaptchaVerifier = new firebase.auth.RecaptchaVerifier('get-otp-btn', {
                'size': 'invisible',
                'callback': (response) => {
                    console.log("reCAPTCHA verified");
                }
            });
        }
        
        console.log("Attempting Firebase SMS...");
        window.confirmationResult = await window.firebaseAuth.signInWithPhoneNumber(phoneNumber, window.recaptchaVerifier);
        isUsingFirebase = true; // Firebase pass ho gaya
        
        showOtpScreen(phoneNumber);
        Toast.success("OTP Sent successfully via SMS");

    } catch (firebaseErr) { 
        console.warn("Firebase SMS Failed. Switching to Local Fallback...", firebaseErr);
        isUsingFirebase = false; // Firebase fail, ab local system use karenge
        
        // 🛠️ PLAN B: Tumhara Local Backend / Render API Fallback
        try {
            const res = await ApiService.post('/notifications/send-otp/', { phone: phoneNumber });
            showOtpScreen(phoneNumber);
            
            if (res.debug_otp) {
                Toast.devOTP(res.debug_otp); 
                const debugOtpStr = String(res.debug_otp);
                const otpInputs = document.querySelectorAll('.otp-input');
                otpInputs.forEach((inp, i) => {
                    if (debugOtpStr[i]) inp.value = debugOtpStr[i];
                });
            } else {
                Toast.success("OTP Sent successfully (Fallback Mode)");
            }
        } catch (localErr) {
            console.error("Local Error Object:", localErr);
            
            // ✅ IMPROVED ERROR HANDLING FOR CLEAN TOAST
            let errorMsg = "Failed to send OTP completely";
            if (localErr.detail) {
                errorMsg = localErr.detail; // Extract direct detail (for Rate Limit)
            } else if (localErr.error) {
                errorMsg = localErr.error;
            } else if (localErr.message) {
                errorMsg = typeof localErr.message === 'string' ? localErr.message : (localErr.message.detail || JSON.stringify(localErr.message));
            }
            
            Toast.error(errorMsg); // Ab ganda JSON nahi aayega
        }
    } finally {
        btn.innerHTML = originalHtml;
        btn.disabled = false;
    }
}

function showOtpScreen(phone) {
    stepPhone.style.display = 'none';
    stepOtp.style.display = 'block';
    document.getElementById('display-phone').innerText = phone;
    startTimerLocal();
    setTimeout(() => {
        const firstInput = document.querySelector('.otp-input');
        if(firstInput) firstInput.focus();
    }, 100);
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
        let requestPayload = {};

        if (isUsingFirebase) {
            // Firebase OTP Verify
            const result = await window.confirmationResult.confirm(otp);
            const idToken = await result.user.getIdToken();
            requestPayload = { login_type: 'firebase', token: idToken }; // Send Firebase Token
        } else {
            // Local OTP Verify
            requestPayload = { login_type: 'local', phone: phoneNumber, otp: otp }; // Send Local OTP
        }

        // Call Tumhari Existing Backend API (Render)
        const res = await ApiService.post('/auth/register/customer/', requestPayload);

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
        console.error("Verification Error Object:", err);
        
        // ✅ IMPROVED ERROR HANDLING FOR CLEAN TOAST
        let errorMsg = "Verification Failed! Wrong OTP.";
        if (err.detail) {
            errorMsg = err.detail; // Extract direct detail
        } else if (err.error) {
            errorMsg = err.error;
        } else if (err.message) {
            errorMsg = typeof err.message === 'string' ? err.message : (err.message.detail || JSON.stringify(err.message));
        }
        
        Toast.error(errorMsg); // Ab ganda JSON nahi aayega
        
        // Agar Firebase se fail hua toh reCAPTCHA reset karna padta hai
        if (isUsingFirebase && window.recaptchaVerifier) {
            window.recaptchaVerifier.clear();
            window.recaptchaVerifier = null;
        }
    } finally {
        btn.disabled = false;
        btn.innerText = originalText;
    }
}

function startTimerLocal() {
    let time = 30;
    const container = document.querySelector('.mt-4.text-muted.small'); 
    
    // Har baar jab timer start ho, toh wapas "Resend OTP in 30s" set karein
    if (container) {
        container.innerHTML = `Resend OTP in <span id="timer">${time}</span>s`;
    }

    const el = document.getElementById('timer');
    if(!el) return;

    const interval = setInterval(() => {
        el.innerText = --time;
        
        if(time <= 0) {
            clearInterval(interval);
            // Jab time 0 ho jaye, toh isko clickable 'Resend OTP' link bana dein
            if (container) {
                container.innerHTML = `<span class="link-text text-primary" style="cursor: pointer; font-weight: bold;" onclick="triggerResend()">Resend OTP</span>`;
            }
        }
    }, 1000);
}

// Resend OTP par click karne se form ko dobara submit karega
window.triggerResend = function() {
    const phoneForm = document.getElementById('step-phone');
    if (phoneForm) {
        // Yeh wapas handleSendOtp function ko call kar dega
        phoneForm.dispatchEvent(new Event('submit'));
    }
}

window.resetForm = function() {
    stepOtp.style.display = 'none';
    stepPhone.style.display = 'block';
    document.getElementById('get-otp-btn').disabled = false;
    document.querySelectorAll('.otp-input').forEach(i => i.value = '');
}