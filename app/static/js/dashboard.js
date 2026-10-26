// Dashboard Charts Initializer
document.addEventListener("DOMContentLoaded", function () {
    // 1. Stock Movement Trend Chart
    const movementCanvas = document.getElementById("movementChart");
    if (movementCanvas && window.dashboardMovementData) {
        const data = window.dashboardMovementData;
        const ctx = movementCanvas.getContext("2d");

        new Chart(ctx, {
            type: "line",
            data: {
                labels: data.labels,
                datasets: [
                    {
                        label: "Incoming (Stock-In)",
                        data: data.incoming,
                        borderColor: "#10b981",
                        backgroundColor: "rgba(16, 185, 129, 0.1)",
                        borderWidth: 2,
                        tension: 0.3,
                        fill: true,
                        pointRadius: 3,
                    },
                    {
                        label: "Outgoing (Stock-Out)",
                        data: data.outgoing,
                        borderColor: "#ef4444",
                        backgroundColor: "rgba(239, 68, 68, 0.08)",
                        borderWidth: 2,
                        tension: 0.3,
                        fill: true,
                        pointRadius: 3,
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: "top",
                        labels: { boxWidth: 12, font: { size: 12 } }
                    },
                    tooltip: {
                        mode: "index",
                        intersect: false
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        grid: { color: "#f1f5f9" },
                        ticks: { precision: 0 }
                    },
                    x: {
                        grid: { display: false }
                    }
                }
            }
        });
    }

    // 2. Category Distribution Doughnut Chart
    const categoryCanvas = document.getElementById("categoryChart");
    if (categoryCanvas && window.dashboardCategoryData) {
        const catData = window.dashboardCategoryData;
        const ctx = categoryCanvas.getContext("2d");

        const palette = [
            "#2563eb", "#0ea5e9", "#10b981", "#f59e0b",
            "#8b5cf6", "#ec4899", "#64748b"
        ];

        new Chart(ctx, {
            type: "doughnut",
            data: {
                labels: catData.labels,
                datasets: [{
                    data: catData.quantities,
                    backgroundColor: palette.slice(0, catData.labels.length),
                    borderWidth: 2,
                    borderColor: "#ffffff"
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                cutout: "68%",
                plugins: {
                    legend: {
                        position: "bottom",
                        labels: { boxWidth: 10, font: { size: 11 }, padding: 12 }
                    },
                    tooltip: {
                        callbacks: {
                            label: function (context) {
                                const val = context.raw || 0;
                                return ` ${context.label}: ${val} units`;
                            }
                        }
                    }
                }
            }
        });
    }

    // Mobile Sidebar Toggle
    const sidebar = document.getElementById("appSidebar");
    const toggleBtn = document.getElementById("sidebarToggleBtn");
    const overlay = document.getElementById("sidebarOverlay");

    if (toggleBtn && sidebar && overlay) {
        toggleBtn.addEventListener("click", function () {
            sidebar.classList.toggle("show");
            overlay.classList.toggle("show");
        });

        overlay.addEventListener("click", function () {
            sidebar.classList.remove("show");
            overlay.classList.remove("show");
        });
    }
});
