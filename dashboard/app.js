const PROXY_URL = "http://localhost:5001";

// Application State
let state = {
    connected: false,
    profile: null,
    margins: null,
    holdings: [],
    positions: [],
    loginUrl: null,
    botStatus: null,
    debateLog: ""
};

// Chart references
let allocationChart = null;

// DOM Elements
const el = {
    statusText: document.getElementById("status-text"),
    statusIndicator: document.getElementById("status-indicator"),
    authSection: document.getElementById("auth-section"),
    dashboardContent: document.getElementById("dashboard-content"),
    loginLinkBtn: document.getElementById("login-link-btn"),
    verifyBtn: document.getElementById("verify-btn"),
    userName: document.getElementById("user-name"),
    userId: document.getElementById("user-id"),
    equityBalance: document.getElementById("equity-balance"),
    portfolioValue: document.getElementById("portfolio-value"),
    dayPnl: document.getElementById("day-pnl"),
    holdingsTable: document.getElementById("holdings-table-body"),
    chatInput: document.getElementById("chat-input"),
    chatSendBtn: document.getElementById("chat-send-btn"),
    chatMessages: document.getElementById("chat-messages"),
    buySellBtn: document.getElementById("buy-sell-btn"),
    tradeSymbol: document.getElementById("trade-symbol"),
    tradeQty: document.getElementById("trade-qty"),
    tradePrice: document.getElementById("trade-price"),
    tradeAction: document.getElementById("trade-action"),
    
    // AI Agent Ticker Elements
    agentActiveStrategy: document.getElementById("agent-active-strategy"),
    agentLastUpdatedLabel: document.getElementById("agent-last-updated-label"),
    readDebateBtn: document.getElementById("read-debate-btn"),
    debateModal: document.getElementById("debate-modal"),
    closeDebateBtn: document.getElementById("close-debate-btn"),
    debateTextContent: document.getElementById("debate-text-content"),
    
    // Active Position Elements
    activeTradeCard: document.getElementById("ai-active-trade-card"),
    activeTradeSymbol: document.getElementById("active-trade-symbol"),
    activeTradeType: document.getElementById("active-trade-type"),
    activeTradeQty: document.getElementById("active-trade-qty"),
    activeTradeEntry: document.getElementById("active-trade-entry"),
    activeTradePnl: document.getElementById("active-trade-pnl"),
    activeTradeHardSl: document.getElementById("active-trade-hard-sl"),
    activeTradeTrailSl: document.getElementById("active-trade-trail-sl"),
    activeTradeHwm: document.getElementById("active-trade-hwm")
};

// Helper function to format currency in Indian Rupees (INR)
function formatCurrency(num) {
    if (isNaN(num)) return "₹0.00";
    return new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR' }).format(num);
}

// Helper function to format percentage
function formatPercent(num) {
    if (isNaN(num)) return "0.00%";
    const prefix = num >= 0 ? "+" : "";
    return `${prefix}${num.toFixed(2)}%`;
}

// Check Proxy status
async function checkConnection() {
    try {
        const resp = await fetch(`${PROXY_URL}/status`);
        const data = await resp.json();
        if (data.status === "healthy") {
            state.connected = true;
            el.statusText.innerText = "Kite Connected";
            el.statusIndicator.classList.add("connected");
            
            // Verify if already authorized
            await checkAuth();
        } else {
            handleDisconnected();
        }
    } catch (e) {
        handleDisconnected();
    }
}

function handleDisconnected() {
    state.connected = false;
    el.statusText.innerText = "Kite Disconnected";
    el.statusIndicator.classList.remove("connected");
    el.authSection.style.display = "block";
    el.dashboardContent.style.display = "none";
}

// Verify authorization state
async function checkAuth() {
    try {
        const resp = await fetch(`${PROXY_URL}/profile`);
        const data = await resp.json();
        
        if (data.result && data.result.content) {
            const profileText = data.result.content[0].text;
            if (profileText.includes("Please log in first")) {
                // Need authentication
                showLoginPrompt();
            } else {
                // Fully authenticated!
                state.profile = JSON.parse(profileText);
                el.authSection.style.display = "none";
                el.dashboardContent.style.display = "grid";
                
                // Render Profile Details
                el.userName.innerText = state.profile.user_name;
                el.userId.innerText = state.profile.user_id;
                
                // Load Portfolio Data
                await loadDashboardData();
            }
        } else if (data.isError) {
            showLoginPrompt();
        }
    } catch (e) {
        console.error("Auth check failed", e);
        showLoginPrompt();
    }
}

// Fetch secure login URL
async function showLoginPrompt() {
    el.authSection.style.display = "block";
    el.dashboardContent.style.display = "none";
    
    try {
        const resp = await fetch(`${PROXY_URL}/login`);
        const data = await resp.json();
        
        if (data.result && data.result.content) {
            const text = data.result.content[0].text;
            // Extract URL from Markdown style: [Login to Kite](URL) or raw URL
            const urlMatch = text.match(/\((https:\/\/kite\.zerodha\.com\/connect\/login[^\)]+)\)/);
            if (urlMatch) {
                state.loginUrl = urlMatch[1];
                el.loginLinkBtn.href = state.loginUrl;
                el.loginLinkBtn.style.display = "inline-flex";
            }
        }
    } catch (e) {
        console.error("Failed to fetch login link", e);
    }
}

// Load all dashboard datasets
async function loadDashboardData() {
    await Promise.all([
        loadMargins(),
        loadHoldings()
    ]);
    
    renderAllocationChart();
}

// Fetch margins
async function loadMargins() {
    try {
        const resp = await fetch(`${PROXY_URL}/margins`);
        const data = await resp.json();
        if (data.result && data.result.content) {
            const marginData = JSON.parse(data.result.content[0].text);
            state.margins = marginData;
            
            // Equity net balance
            const balance = marginData.equity ? marginData.equity.available.live_balance : 0;
            el.equityBalance.innerText = formatCurrency(balance);
            if (balance < 0) {
                el.equityBalance.classList.add("loss-text");
            } else {
                el.equityBalance.classList.remove("loss-text");
            }
        }
    } catch (e) {
        console.error("Failed to load margins", e);
    }
}

// Fetch holdings
async function loadHoldings() {
    try {
        const resp = await fetch(`${PROXY_URL}/holdings`);
        const data = await resp.json();
        if (data.result && data.result.content) {
            const holdingsList = JSON.parse(data.result.content[0].text);
            state.holdings = holdingsList;
            
            // Render holdings list in table
            renderHoldingsTable();
            
            // Calculate total portfolio metrics
            let totalValue = 0;
            let totalCost = 0;
            let dayPnlSum = 0;
            
            holdingsList.forEach(item => {
                const value = item.quantity * item.last_price;
                const cost = item.quantity * item.average_price;
                totalValue += value;
                totalCost += cost;
                
                // Calculate day change value
                const prevCloseVal = item.quantity * item.close_price;
                dayPnlSum += (value - prevCloseVal);
            });
            
            el.portfolioValue.innerText = formatCurrency(totalValue);
            
            // Total Portfolio PNL
            const totalPnl = totalValue - totalCost;
            const totalPnlPct = totalCost > 0 ? (totalPnl / totalCost) * 100 : 0;
            
            // Render day PNL status
            el.dayPnl.innerText = `${formatCurrency(dayPnlSum)} (${formatPercent(dayPnlSum / totalCost * 100)})`;
            if (dayPnlSum >= 0) {
                el.dayPnl.className = "stat-value gain-text";
            } else {
                el.dayPnl.className = "stat-value loss-text";
            }
        }
    } catch (e) {
        console.error("Failed to load holdings", e);
    }
}

// Render Holdings Table
function renderHoldingsTable() {
    el.holdingsTable.innerHTML = "";
    
    state.holdings.forEach(item => {
        const value = item.quantity * item.last_price;
        const cost = item.quantity * item.average_price;
        const pnl = value - cost;
        const pnlPct = cost > 0 ? (pnl / cost) * 100 : 0;
        
        const tr = document.createElement("tr");
        tr.innerHTML = `
            <td class="symbol-cell">
                <div>${item.tradingsymbol}</div>
                <div class="symbol-name">${item.exchange} | ${item.isin}</div>
            </td>
            <td class="number-cell">${item.quantity}</td>
            <td class="number-cell">${formatCurrency(item.average_price)}</td>
            <td class="number-cell">${formatCurrency(item.last_price)}</td>
            <td class="number-cell">${formatCurrency(value)}</td>
            <td class="number-cell ${pnl >= 0 ? 'gain-text' : 'loss-text'}">
                ${formatCurrency(pnl)} (${formatPercent(pnlPct)})
            </td>
        `;
        
        // Click table row to pre-fill order ticket
        tr.style.cursor = "pointer";
        tr.addEventListener("click", () => {
            el.tradeSymbol.value = item.tradingsymbol;
            el.tradePrice.value = item.last_price;
        });
        
        el.holdingsTable.appendChild(tr);
    });
}

// Render Holdings Allocation Chart
function renderAllocationChart() {
    if (allocationChart) {
        allocationChart.destroy();
    }
    
    const ctx = document.getElementById("allocation-chart").getContext("2d");
    
    const labels = state.holdings.map(h => h.tradingsymbol);
    const values = state.holdings.map(h => h.quantity * h.last_price);
    
    // Curated modern color palette
    const colors = [
        "HSL(263.4 70% 50.4%)", // purple
        "HSL(142.1 70.6% 45.3%)", // emerald
        "HSL(210 100% 50%)", // blue
        "HSL(36 100% 50%)", // orange
        "HSL(280 80% 60%)", // magenta
    ];
    
    allocationChart = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: labels,
            datasets: [{
                data: values,
                backgroundColor: colors.slice(0, labels.length),
                borderColor: "HSL(240 10% 6%)",
                borderWidth: 2
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'right',
                    labels: {
                        color: "HSL(240 5% 96%)",
                        font: {
                            family: 'Outfit'
                        }
                    }
                }
            }
        }
    });
}

// Perform trade (Mock Order Panel)
async function performTrade() {
    const symbol = el.tradeSymbol.value.trim().toUpperCase();
    const qty = parseInt(el.tradeQty.value);
    const price = parseFloat(el.tradePrice.value);
    const action = el.tradeAction.value;
    
    if (!symbol || isNaN(qty) || qty <= 0 || isNaN(price) || price <= 0) {
        alert("Please fill in all trade details with valid values.");
        return;
    }
    
    el.buySellBtn.disabled = true;
    el.buySellBtn.innerText = "Processing...";
    
    // Since live order placement is restricted/disabled on the hosted Kite MCP server,
    // we catch the expected restriction gracefully and explain it beautifully!
    try {
        const resp = await fetch(`${PROXY_URL}/call`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                name: "place_order",
                arguments: {
                    exchange: "NSE",
                    tradingsymbol: symbol,
                    transaction_type: action.toUpperCase(),
                    quantity: qty,
                    price: price,
                    order_type: "LIMIT",
                    product: "CNC",
                    validity: "DAY"
                }
            })
        });
        const data = await resp.json();
        
        if (data.error || data.isError) {
            const errMsg = data.error || data.result.content[0].text;
            showTradeAlert(errMsg);
        } else {
            alert(`Order placed successfully! ID: ${data.result.order_id}`);
        }
    } catch (e) {
        showTradeAlert("Order placement is disabled on the hosted Kite MCP server for security. To enable live order execution, please self-host the server locally with your own credentials.");
    } finally {
        el.buySellBtn.disabled = false;
        el.buySellBtn.innerText = `${action === 'buy' ? 'Buy' : 'Sell'} ${symbol}`;
    }
}

function showTradeAlert(message) {
    // Create a sleek modal dialog for trade restriction
    const modal = document.createElement("div");
    modal.style.position = "fixed";
    modal.style.top = "0";
    modal.style.left = "0";
    modal.style.width = "100%";
    modal.style.height = "100%";
    modal.style.background = "rgba(0,0,0,0.85)";
    modal.style.display = "flex";
    modal.style.alignItems = "center";
    modal.style.justifyContent = "center";
    modal.style.zIndex = "1000";
    
    modal.innerHTML = `
        <div class="card" style="max-width: 450px; padding: 2rem; text-align: center;">
            <div class="auth-icon" style="color: HSL(36 100% 50%); background: HSL(36 100% 50% / 0.1); margin: 0 auto 1.5rem auto;">
                ⚠️
            </div>
            <h3 style="margin-bottom: 1rem; font-size: 1.25rem;">Live Trading Restricted</h3>
            <p style="font-size: 0.9rem; color: var(--text-muted); line-height: 1.6; margin-bottom: 1.5rem;">
                The hosted Zerodha Kite MCP server excludes active trading operations (like buying or selling) for user protection.
                <br><br>
                To trade live directly from this dashboard, configure your own API keys and self-host the Kite MCP Go server locally.
            </p>
            <button class="btn" id="close-alert-btn" style="background: HSL(240 5.9% 15%); color: var(--text);">Close</button>
        </div>
    `;
    
    document.body.appendChild(modal);
    document.getElementById("close-alert-btn").addEventListener("click", () => {
        modal.remove();
    });
}

// Sidebar AI Trading Assistant Chat
function appendMessage(role, text) {
    const msgDiv = document.createElement("div");
    msgDiv.className = `message ${role}`;
    msgDiv.innerText = text;
    el.chatMessages.appendChild(msgDiv);
    el.chatMessages.scrollTop = el.chatMessages.scrollHeight;
}

function handleAIChat() {
    const input = el.chatInput.value.trim();
    if (!input) return;
    
    appendMessage("user", input);
    el.chatInput.value = "";
    
    // Mock AI context-aware analysis
    setTimeout(() => {
        const lower = input.toLowerCase();
        let response = "I can analyze your portfolio, holdings, margins, and calculate stock metrics. What would you like to know?";
        
        if (lower.includes("portfolio") || lower.includes("holdings")) {
            const symbols = state.holdings.map(h => h.tradingsymbol).join(", ");
            response = `Your portfolio contains ${state.holdings.length} holdings: ${symbols}. Your total asset value is ${el.portfolioValue.innerText}.`;
        } else if (lower.includes("best") || lower.includes("top") || lower.includes("profit")) {
            const best = [...state.holdings].sort((a,b) => (b.quantity*b.last_price - b.quantity*b.average_price) - (a.quantity*a.last_price - a.quantity*a.average_price))[0];
            if (best) {
                const pnl = best.quantity * (best.last_price - best.average_price);
                response = `Your top performing stock is ${best.tradingsymbol} with a total unrealized gain of ${formatCurrency(pnl)} (+${((best.last_price - best.average_price)/best.average_price * 100).toFixed(2)}%)!`;
            }
        } else if (lower.includes("worst") || lower.includes("loss") || lower.includes("down")) {
            const worst = [...state.holdings].sort((a,b) => (a.quantity*a.last_price - a.quantity*a.average_price) - (b.quantity*b.last_price - b.quantity*b.average_price))[0];
            if (worst) {
                const pnl = worst.quantity * (worst.last_price - worst.average_price);
                response = `Your worst performing stock is ${worst.tradingsymbol} with a total unrealized loss of ${formatCurrency(pnl)} (${((worst.last_price - worst.average_price)/worst.average_price * 100).toFixed(2)}%).`;
            }
        } else if (lower.includes("margin") || lower.includes("balance") || lower.includes("cash")) {
            response = `Your active equity available margin balance is ${el.equityBalance.innerText}.`;
        }
        
        appendMessage("assistant", response);
    }, 1000);
}

// Event Listeners
el.verifyBtn.addEventListener("click", checkConnection);
el.buySellBtn.addEventListener("click", performTrade);
el.chatSendBtn.addEventListener("click", handleAIChat);
el.chatInput.addEventListener("keypress", (e) => {
    if (e.key === "Enter") handleAIChat();
});

// Quick trade action toggle (changes button colors)
el.tradeAction.addEventListener("change", (e) => {
    const action = e.target.value;
    el.buySellBtn.innerText = `${action === 'buy' ? 'Buy' : 'Sell'} ${el.tradeSymbol.value.toUpperCase() || 'STOCK'}`;
    if (action === 'buy') {
        el.buySellBtn.style.backgroundColor = "var(--emerald)";
    } else {
        el.buySellBtn.style.backgroundColor = "var(--rose)";
    }
});

el.tradeSymbol.addEventListener("input", (e) => {
    const symbol = e.target.value.toUpperCase();
    el.buySellBtn.innerText = `${el.tradeAction.value === 'buy' ? 'Buy' : 'Sell'} ${symbol || 'STOCK'}`;
});

// Poll AI Bot status & debate logs periodically
async function pollBotStatus() {
    try {
        const resp = await fetch(`${PROXY_URL}/bot_status`, { cache: "no-store" });
        if (!resp.ok) return;
        
        const data = await resp.json();
        state.botStatus = data;
        
        // Render strategy name
        el.agentActiveStrategy.innerText = data.active_strategy.replace(/_/g, " ");
        
        // Render state & mode label
        el.agentLastUpdatedLabel.innerText = `State: ${data.status} | Mode: ${data.trading_mode} | Sentiment: ${data.day_sentiment} (Synced: ${data.last_updated})`;
        
        // If debate logs exist, show button
        if (data.debate_log) {
            state.debateLog = data.debate_log;
            el.readDebateBtn.style.display = "inline-flex";
        } else {
            el.readDebateBtn.style.display = "none";
        }
        
        
        // If in a position, display active position card
        if (data.active_position) {
            const pos = data.active_position;
            el.activeTradeSymbol.innerText = pos.symbol;
            el.activeTradeType.innerText = pos.type;
            el.activeTradeQty.innerText = pos.quantity;
            el.activeTradeEntry.innerText = formatCurrency(pos.entry_price);
            
            // Render Live P&L
            const livePnl = pos.live_pnl || 0.0;
            el.activeTradePnl.innerText = formatCurrency(livePnl);
            if (livePnl >= 0) {
                el.activeTradePnl.className = "gain-text";
                el.activeTradeCard.style.borderColor = "var(--emerald)";
            } else {
                el.activeTradePnl.className = "loss-text";
                el.activeTradeCard.style.borderColor = "var(--rose)";
            }
            
            el.activeTradeHardSl.innerText = formatCurrency(pos.initial_stop_loss);
            el.activeTradeTrailSl.innerText = formatCurrency(pos.trailing_stop_loss);
            el.activeTradeHwm.innerText = formatCurrency(pos.high_water_mark);
            
            el.activeTradeCard.style.display = "flex";
        } else {
            el.activeTradeCard.style.display = "none";
        }
        
        // Render Live Console Logs
        const consoleContainer = document.getElementById("console-log-container");
        if (consoleContainer && data.latest_logs && Array.isArray(data.latest_logs)) {
            let newHTML = "";
            
            data.latest_logs.forEach(log => {
                let logColor = "var(--text-muted)";
                if (log.includes("🛒") || log.includes("BUY") || log.includes("Entered") || log.includes("COMPLETE") || log.includes("PROFIT") || log.includes("Prime")) {
                    logColor = "var(--emerald)";
                } else if (log.includes("❌") || log.includes("SELL") || log.includes("Stopped") || log.includes("failed") || log.includes("REJECTED") || log.includes("SL hit") || log.includes("BLOCKED")) {
                    logColor = "var(--rose)";
                } else if (log.includes("🎯") || log.includes("🚨") || log.includes("TSL") || log.includes("trailed") || log.includes("Re-assessing") || log.includes("assessment")) {
                    logColor = "HSL(36 100% 50%)"; // orange highlight
                } else if (log.includes("AWAITING_SIGNAL") || log.includes("SETUP") || log.includes("🤖")) {
                    logColor = "HSL(263.4 70% 70%)"; // light purple
                }
                
                newHTML += `<div style="color: ${logColor}; font-size: 0.72rem; margin-bottom: 0.15rem;">${log}</div>`;
            });
            
            if (newHTML && consoleContainer.innerHTML !== newHTML) {
                consoleContainer.innerHTML = newHTML;
                consoleContainer.scrollTop = consoleContainer.scrollHeight;
            }
        }
    } catch (e) {
        // Ignore file-absent errors on startup
    }
}

// Debate Modal Show/Hide
function showDebateModal() {
    if (!state.debateLog) return;
    
    // Beautify the debate logs before displaying
    let htmlContent = state.debateLog
        .replace(/\[Alpha Strategist's Pitch\]:/g, '<strong style="color: var(--primary); font-size: 1.05rem; display: block; margin-top: 1rem; margin-bottom: 0.25rem;">🟢 [Alpha Strategist\'s Pitch]</strong>')
        .replace(/\[Risk Manager's Critique\]:/g, '<strong style="color: var(--rose); font-size: 1.05rem; display: block; margin-top: 1.5rem; margin-bottom: 0.25rem;">🔴 [Risk Manager\'s Critique]</strong>')
        .replace(/\[Consensus Verdict\]:/g, '<strong style="color: var(--emerald); font-size: 1.05rem; display: block; margin-top: 1.5rem; margin-bottom: 0.25rem;">⚖️ [Consensus Verdict]</strong>');
        
    el.debateTextContent.innerHTML = htmlContent;
    el.debateModal.style.display = "flex";
}

function hideDebateModal() {
    el.debateModal.style.display = "none";
}

// Event listeners for debate modal
el.readDebateBtn.addEventListener("click", showDebateModal);
el.closeDebateBtn.addEventListener("click", hideDebateModal);
el.debateModal.addEventListener("click", (e) => {
    if (e.target === el.debateModal) hideDebateModal();
});

// Initial Connection check
checkConnection();

// Start AI Bot Ticker Poll (every 3 seconds)
pollBotStatus();
setInterval(pollBotStatus, 3000);
