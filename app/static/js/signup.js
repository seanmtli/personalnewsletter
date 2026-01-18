// Signup flow JavaScript
// Handles localStorage persistence and form submission

const STORAGE_KEY = 'signup_interests';

// Save interests to localStorage
function saveInterestsToStorage(interests, teamsData, athletesData) {
    const preferencesData = interests.map(name => {
        const data = findInterestDataForStorage(name, teamsData, athletesData);
        let type = 'custom';
        if (data) {
            for (const league in teamsData) {
                if (teamsData[league].some(t => t.name === name)) {
                    type = 'team';
                    break;
                }
            }
            for (const sport in athletesData) {
                if (athletesData[sport].some(a => a.name === name)) {
                    type = 'athlete';
                    break;
                }
            }
        }
        return {
            interest_type: type,
            interest_name: name,
            interest_data: data || null
        };
    });

    localStorage.setItem(STORAGE_KEY, JSON.stringify(preferencesData));
}

function findInterestDataForStorage(name, teamsData, athletesData) {
    for (const league in teamsData) {
        const team = teamsData[league].find(t => t.name === name);
        if (team) return team;
    }
    for (const sport in athletesData) {
        const athlete = athletesData[sport].find(a => a.name === name);
        if (athlete) return athlete;
    }
    return null;
}

// Load interests from localStorage
function loadInterestsFromStorage() {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored) {
        try {
            return JSON.parse(stored);
        } catch (e) {
            console.error('Error parsing stored interests:', e);
        }
    }
    return [];
}

// Get just the names of stored interests
function getStoredInterestNames() {
    const preferences = loadInterestsFromStorage();
    return new Set(preferences.map(p => p.interest_name));
}

// Clear stored interests
function clearStoredInterests() {
    localStorage.removeItem(STORAGE_KEY);
}

// Continue to email page
function continueToEmail() {
    const interests = loadInterestsFromStorage();
    if (interests.length === 0) {
        alert('Please select at least one team or athlete before continuing.');
        return;
    }
    window.location.href = '/signup/email';
}

// Submit signup with email
async function submitSignup(email) {
    const preferences = loadInterestsFromStorage();

    if (preferences.length === 0) {
        alert('No interests selected. Please go back and select some teams or athletes.');
        return false;
    }

    try {
        const response = await fetch('/signup/complete', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                email: email,
                preferences: preferences
            }),
        });

        if (response.ok) {
            clearStoredInterests();
            window.location.href = '/signup/success';
            return true;
        } else {
            const data = await response.json();
            throw new Error(data.detail || 'Signup failed');
        }
    } catch (error) {
        alert('Error: ' + error.message);
        return false;
    }
}

// Email form handler
function initEmailForm() {
    const form = document.getElementById('email-form');
    if (!form) return;

    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        const emailInput = document.getElementById('email');
        const submitBtn = document.getElementById('submit-btn');
        const email = emailInput.value.trim();

        if (!email) {
            alert('Please enter your email address.');
            return;
        }

        // Disable button during submission
        submitBtn.disabled = true;
        submitBtn.textContent = 'Signing up...';

        const success = await submitSignup(email);

        if (!success) {
            submitBtn.disabled = false;
            submitBtn.textContent = 'Sign Up';
        }
    });

    // Show selected interests count
    const interests = loadInterestsFromStorage();
    const countEl = document.getElementById('interests-count');
    if (countEl) {
        countEl.textContent = interests.length;
    }

    // Show interest summary
    const summaryEl = document.getElementById('interests-summary');
    if (summaryEl && interests.length > 0) {
        const names = interests.map(p => p.interest_name);
        if (names.length <= 3) {
            summaryEl.textContent = names.join(', ');
        } else {
            summaryEl.textContent = names.slice(0, 3).join(', ') + ` and ${names.length - 3} more`;
        }
    }
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    initEmailForm();
});
