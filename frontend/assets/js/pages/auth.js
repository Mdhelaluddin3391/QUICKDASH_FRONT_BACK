// assets/js/pages/auth.js

let isUsingFirebase = false; // Variable rakha hai taaki errors na aayein
let confirmationResult = null; // Isey bhi safe rakha hai
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

    // 🔥 Advanced & Smooth OTP Input Logic (No changes here)
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
        
        isUsingFirebase = false; // Always force local validation now
        
        const res = await ApiService.post('/notifications/send-otp/', { phone: phoneNumber });
        showOtpScreen(phoneNumber);
        
        // Smart Fallback: Agar Twilio fail ho ya debug mode ho
        if (res.debug_otp) {
            Toast.devOTP(res.debug_otp); 
            const debugOtpStr = String(res.debug_otp);
            const otpInputs = document.querySelectorAll('.otp-input');
            otpInputs.forEach((inp, i) => {
                if (debugOtpStr[i]) inp.value = debugOtpStr[i];
            });
        } else {
            Toast.success("OTP Sent successfully via SMS"); // Backend handled Twilio successfully
        }

    } catch (err) {
        console.error("Local Error Object:", err);
        
        // ✅ IMPROVED ERROR HANDLING FOR CLEAN TOAST
        let errorMsg = "Failed to send OTP completely";
        if (err.detail) {
            errorMsg = err.detail; 
        } else if (err.error) {
            errorMsg = err.error;
        } else if (err.message) {
            errorMsg = typeof err.message === 'string' ? err.message : (err.message.detail || JSON.stringify(err.message));
        }
        
        Toast.error(errorMsg);
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
        let requestPayload = { login_type: 'local', phone: phoneNumber, otp: otp }; 

        // Call Tumhari Existing Backend API (Render)
        const res = await ApiService.post('/auth/register/customer/', requestPayload);

        if (res.access) {
            localStorage.setItem(APP_CONFIG.STORAGE_KEYS.TOKEN, res.access);
            if(res.refresh) localStorage.setItem(APP_CONFIG.STORAGE_KEYS.REFRESH, res.refresh);
            
            try {
                const user = await ApiService.get('/auth/me/');
                localStorage.setItem(APP_CONFIG.STORAGE_KEYS.USER, JSON.stringify(user));

                // 🔥 NAYA CODE YAHAN HAI: Login hote hi address fetch karke L2 set karna 🔥
                try {
                    const addrRes = await ApiService.get('/customers/addresses/'); 
                    const addresses = addrRes.results || addrRes || [];
                    
                    if (addresses.length > 0) {
                        const defAddr = addresses.find(a => a.is_default) || addresses[0];
                        
                        if (window.LocationManager) {
                            window.LocationManager.setDeliveryAddress({
                                id: defAddr.id,
                                lat: defAddr.latitude || defAddr.lat,
                                lng: defAddr.longitude || defAddr.lng,
                                address_line: defAddr.address_line_1 || defAddr.address_line || 'Saved Address',
                                city: defAddr.city || '',
                                label: defAddr.address_type || 'Delivery'
                            });
                            console.log("[Auth] Existing L2 Address Auto-Set!");
                        }
                    }
                } catch (addrErr) {
                    console.warn("Silently failed to fetch addresses on login", addrErr);
                }
                // 🔥 NAYA CODE KHATAM 🔥

            } catch(e) { console.warn("Profile fetch failed", e); }
            
            Toast.success("Login Successful");
            ApiService.clearCache();
            window.location.href = APP_CONFIG.ROUTES.HOME;
        } else {
            throw new Error("No access token received");
        }

    } catch (err) {
        console.error("Local Error Object:", err);
        
        let errorMsg = "Kuch galat ho gaya, kripya dobara koshish karein.";
        
        // 1. Agar ApiService ne data object bheja hai (DRF Throttle Response handle karne ke liye)
        if (err.data && err.data.detail) {
            errorMsg = err.data.detail;
        } 
        // 2. Agar message JSON string ban gaya hai toh usko parse karke message nikalenge
        else if (err.message) {
            try {
                let parsedError = JSON.parse(err.message);
                // Agar parsed JSON ke andar 'detail' ya 'error' field hai
                errorMsg = parsedError.detail || parsedError.error || err.message;
            } catch (e) {
                // Agar JSON parse nahi hua, matlab normal string hai
                errorMsg = err.message;
            }
        }
        
        Toast.error(errorMsg);
    } finally {
        btn.disabled = false;
        btn.innerText = originalText;
    }
}

function startTimerLocal() {
    let time = 30;
    const container = document.querySelector('.mt-4.text-muted.small'); 
    
    if (container) {
        container.innerHTML = `Resend OTP in <span id="timer">${time}</span>s`;
    }

    const el = document.getElementById('timer');
    if(!el) return;

    const interval = setInterval(() => {
        el.innerText = --time;
        
        if(time <= 0) {
            clearInterval(interval);
            if (container) {
                container.innerHTML = `<span class="link-text text-primary" style="cursor: pointer; font-weight: bold;" onclick="triggerResend()">Resend OTP</span>`;
            }
        }
    }, 1000);
}

window.triggerResend = function() {
    const phoneForm = document.getElementById('step-phone');
    if (phoneForm) {
        phoneForm.dispatchEvent(new Event('submit'));
    }
}

window.resetForm = function() {
    stepOtp.style.display = 'none';
    stepPhone.style.display = 'block';
    document.getElementById('get-otp-btn').disabled = false;
    document.querySelectorAll('.otp-input').forEach(i => i.value = '');
}