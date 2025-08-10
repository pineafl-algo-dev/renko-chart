document.addEventListener('DOMContentLoaded', function() {
    fetch('/renko-data')
        .then(response => response.json())
        .then(data => {
            const chartOptions = {
                layout: {
                    textColor: 'white',
                    background: { type: 'solid', color: '#1a1a1a' },
                },
                grid: {
                    vertLines: { color: '#333' },
                    horzLines: { color: '#333' },
                },
            };

            const chart = LightweightCharts.createChart(document.getElementById('chart'), chartOptions);

            const renkoSeries = chart.addCandlestickSeries({
                upColor: '#26a69a',
                downColor: '#ef5350',
                borderVisible: false,
                wickVisible: true,
            });

            // Map your data to the format expected by Lightweight Charts
            const formattedData = data.map(item => ({
                time: new Date(item.date).getTime() / 1000, // Convert ISO date string to Unix timestamp in seconds
                open: parseFloat(item.open),
                high: parseFloat(item.high),
                low: parseFloat(item.low),
                close: parseFloat(item.close),
            }));

            chart.applyOptions({
                timeScale: {
                    timeVisible: true,
                    secondsVisible: false,
                },
            });

            renkoSeries.setData(formattedData);

            chart.applyOptions({
                timeScale: {
                    timeVisible: true,
                    secondsVisible: false,
                },
            });

            chart.resize(document.getElementById('chart').clientWidth, 400);
        })
        .catch(error => {
            console.error('Error fetching Renko data:', error);
        });
});