// Analytics Page Charts Initializer
document.addEventListener("DOMContentLoaded", function () {
    // 1. Daily Movement Comparison Bar Chart
    const netFlowCanvas = document.getElementById("analyticsFlowChart");
    if (netFlowCanvas && window.analyticsMovementData) {
        const data = window.analyticsMovementData;
        const ctx = netFlowCanvas.getContext("2d");

        new Chart(ctx, {
            type: "bar",
            data: {
                labels: data.labels,
                datasets: [
                    {
                        label: "Inbound Units",
                        data: data.incoming,
                        backgroundColor: "#10b981",
                        borderRadius: 4,
                    },
                    {
                        label: "Outbound Units",
                        data: data.outgoing,
                        backgroundColor: "#ef4444",
                        borderRadius: 4,
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { position: "top" },
                    tooltip: { mode: "index", intersect: false }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        ticks: { precision: 0 },
                        grid: { color: "#f1f5f9" }
                    },
                    x: {
                        grid: { display: false }
                    }
                }
            }
        });
    }

    // 2. Category Cost Valuation Bar Chart
    const categoryValueCanvas = document.getElementById("categoryValueChart");
    if (categoryValueCanvas && window.analyticsCategoryData) {
        const catData = window.analyticsCategoryData;
        const ctx = categoryValueCanvas.getContext("2d");

        new Chart(ctx, {
            type: "bar",
            data: {
                labels: catData.labels,
                datasets: [{
                    label: "Inventory Value ($)",
                    data: catData.cost_values,
                    backgroundColor: "#2563eb",
                    borderRadius: 4
                }]
            },
            options: {
                indexAxis: "y",
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        callbacks: {
                            label: function (ctx) {
                                return ` Value: $${ctx.raw.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
                            }
                        }
                    }
                },
                scales: {
                    x: {
                        beginAtZero: true,
                        grid: { color: "#f1f5f9" },
                        ticks: {
                            callback: function (val) {
                                return "$" + val.toLocaleString();
                            }
                        }
                    },
                    y: {
                        grid: { display: false }
                    }
                }
            }
        });
    }
});
