// Interest picker functionality

let teamsData = {};
let athletesData = {};
let selectedInterests = new Set();

function initializePicker(teams, athletes, existing) {
    teamsData = teams;
    athletesData = athletes;
    selectedInterests = existing;

    // Render teams
    renderTeams('nfl', 'nfl-teams');
    renderTeams('nba', 'nba-teams');
    renderTeams('mlb', 'mlb-teams');
    renderTeams('nhl', 'nhl-teams');
    renderTeams('premier_league', 'premier-teams');
    renderTeams('mls', 'mls-teams');

    // Render athletes
    renderAthletes('nfl', 'nfl-athletes');
    renderAthletes('nba', 'nba-athletes');
    renderAthletes('mlb', 'mlb-athletes');
    renderAthletes('nhl', 'nhl-athletes');
    renderAthletes('soccer', 'soccer-athletes');

    updateSelectedDisplay();
}

function renderTeams(league, containerId) {
    const container = document.getElementById(containerId);
    if (!container) return;

    const teams = teamsData[league] || [];
    container.innerHTML = teams.map(team => createCard(team, 'team')).join('');
}

function renderAthletes(sport, containerId) {
    const container = document.getElementById(containerId);
    if (!container) return;

    const athletes = athletesData[sport] || [];
    container.innerHTML = athletes.map(athlete => createCard(athlete, 'athlete')).join('');
}

function createCard(item, type) {
    const isSelected = selectedInterests.has(item.name);
    const selectedClass = isSelected ? 'ring-2 ring-indigo-500 bg-indigo-50' : 'hover:bg-gray-50';

    return `
        <div class="picker-card cursor-pointer rounded-lg border p-2 text-center transition-all ${selectedClass}"
             onclick="toggleInterest('${escapeHtml(item.name)}', '${type}', ${JSON.stringify(item).replace(/"/g, '&quot;')})"
             data-name="${escapeHtml(item.name)}">
            <div class="w-10 h-10 mx-auto mb-1 flex items-center justify-center">
                ${item.logo_url || item.photo_url
                    ? `<img src="${item.logo_url || item.photo_url}" alt="${escapeHtml(item.name)}" class="max-w-full max-h-full object-contain rounded">`
                    : `<div class="w-10 h-10 bg-gray-200 rounded-full flex items-center justify-center text-gray-500 text-xs">${item.name.charAt(0)}</div>`
                }
            </div>
            <p class="text-xs text-gray-700 truncate">${escapeHtml(item.name)}</p>
            ${isSelected ? '<span class="text-xs text-indigo-600">✓</span>' : ''}
        </div>
    `;
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function toggleInterest(name, type, data) {
    if (selectedInterests.has(name)) {
        selectedInterests.delete(name);
    } else {
        selectedInterests.add(name);
    }

    // Re-render the card to show selection state
    const cards = document.querySelectorAll(`[data-name="${CSS.escape(name)}"]`);
    cards.forEach(card => {
        if (selectedInterests.has(name)) {
            card.classList.add('ring-2', 'ring-indigo-500', 'bg-indigo-50');
            card.classList.remove('hover:bg-gray-50');
        } else {
            card.classList.remove('ring-2', 'ring-indigo-500', 'bg-indigo-50');
            card.classList.add('hover:bg-gray-50');
        }
    });

    updateSelectedDisplay();
}

function removeInterest(name) {
    selectedInterests.delete(name);

    // Update card appearance
    const cards = document.querySelectorAll(`[data-name="${CSS.escape(name)}"]`);
    cards.forEach(card => {
        card.classList.remove('ring-2', 'ring-indigo-500', 'bg-indigo-50');
        card.classList.add('hover:bg-gray-50');
    });

    updateSelectedDisplay();
}

function updateSelectedDisplay() {
    const container = document.getElementById('selected-interests');
    const noInterests = document.getElementById('no-interests');

    if (selectedInterests.size === 0) {
        container.innerHTML = '';
        noInterests.classList.remove('hidden');
    } else {
        noInterests.classList.add('hidden');

        // Get data for each interest
        const chips = Array.from(selectedInterests).map(name => {
            const data = findInterestData(name);
            const logoHtml = data && (data.logo_url || data.photo_url)
                ? `<img src="${data.logo_url || data.photo_url}" alt="" class="w-4 h-4 mr-1 rounded">`
                : '';

            return `
                <span class="interest-chip inline-flex items-center px-3 py-1 rounded-full text-sm bg-indigo-100 text-indigo-800"
                      data-name="${escapeHtml(name)}">
                    ${logoHtml}
                    ${escapeHtml(name)}
                    <button onclick="removeInterest('${escapeHtml(name)}')" class="ml-2 text-indigo-600 hover:text-indigo-800">&times;</button>
                </span>
            `;
        });

        container.innerHTML = chips.join('');
    }

    // Call localStorage hook for signup flow if available
    if (typeof saveInterestsToStorage === 'function' && typeof teamsData !== 'undefined') {
        saveInterestsToStorage(Array.from(selectedInterests), teamsData, athletesData);
    }
}

function findInterestData(name) {
    // Search teams
    for (const league in teamsData) {
        const team = teamsData[league].find(t => t.name === name);
        if (team) return team;
    }
    // Search athletes
    for (const sport in athletesData) {
        const athlete = athletesData[sport].find(a => a.name === name);
        if (athlete) return athlete;
    }
    return null;
}

function switchTab(tabName) {
    // Update tab buttons
    document.querySelectorAll('.tab-btn').forEach(btn => {
        if (btn.dataset.tab === tabName) {
            btn.classList.add('border-indigo-500', 'text-indigo-600');
            btn.classList.remove('border-transparent', 'text-gray-500');
        } else {
            btn.classList.remove('border-indigo-500', 'text-indigo-600');
            btn.classList.add('border-transparent', 'text-gray-500');
        }
    });

    // Update tab content
    document.querySelectorAll('.tab-content').forEach(content => {
        content.classList.add('hidden');
    });
    document.getElementById('tab-' + tabName).classList.remove('hidden');
}

function addCustomInterest() {
    const input = document.getElementById('custom-interest');
    const name = input.value.trim();

    if (!name) {
        alert('Please enter an interest');
        return;
    }

    if (selectedInterests.has(name)) {
        alert('This interest is already added');
        return;
    }

    selectedInterests.add(name);
    input.value = '';
    updateSelectedDisplay();
}

async function savePreferences() {
    const preferences = Array.from(selectedInterests).map(name => {
        const data = findInterestData(name);
        let type = 'custom';
        if (data) {
            // Check if it's a team or athlete
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

    try {
        const response = await fetch('/preferences/api/bulk', {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ preferences }),
        });

        if (response.ok) {
            window.location.href = '/dashboard';
        } else {
            const data = await response.json();
            alert('Error saving preferences: ' + (data.detail || 'Unknown error'));
        }
    } catch (error) {
        alert('Error saving preferences: ' + error.message);
    }
}

// Handle Enter key in custom interest input
document.addEventListener('DOMContentLoaded', () => {
    const input = document.getElementById('custom-interest');
    if (input) {
        input.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                addCustomInterest();
            }
        });
    }
});
