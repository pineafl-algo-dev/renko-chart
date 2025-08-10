#!/usr/bin/env python3
"""
Renko Chart Server - Ubuntu Production Version
Run with: python3 app.py
Access at: http://YOUR_SERVER_IP:8000
"""

from flask import Flask, jsonify, render_template_string
from flask_cors import CORS
import pandas as pd
import mplfinance as mpf
import json
from datetime import datetime
import warnings
import os
import sys
import logging
import signal
import socket
from threading import Thread
import time

# Suppress pandas warnings
warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=UserWarning)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/renko-chart.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app, origins=["*"])  # Allow all origins for Ubuntu server

# Global variables
renko_df = None
server_stats = {
    'start_time': datetime.now(),
    'requests_served': 0,
    'data_refreshes': 0,
    'errors': 0
}

# HTML template optimized for Ubuntu server
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Renko Chart - Ubuntu Server</title>
  <script src="https://unpkg.com/lightweight-charts@4.1.3/dist/lightweight-charts.standalone.production.js"></script>
  <style>
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body {
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
      background-color: #131722; color: #d1d4dc; padding: 20px;
    }
    .container { max-width: 1400px; margin: 0 auto; }
    .header { text-align: center; margin-bottom: 30px; }
    .header h1 { color: #ffffff; font-size: 2.5rem; font-weight: 600; margin-bottom: 10px; }
    .header p { color: #b2b5be; font-size: 1.1rem; }
    .server-info {
      background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
      color: white; padding: 15px; border-radius: 8px; margin-bottom: 20px;
      text-align: center; box-shadow: 0 4px 12px rgba(0,0,0,0.3);
    }
    .chart-container {
      background-color: #1e222d; border-radius: 8px; padding: 20px;
      box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3); margin-bottom: 20px;
    }
    #chart { width: 100%; height: 600px; border-radius: 4px; }
    .controls {
      background-color: #1e222d; border-radius: 8px; padding: 20px; margin-bottom: 20px;
      display: flex; align-items: center; gap: 15px; flex-wrap: wrap;
    }
    .controls button {
      background-color: #2962ff; color: white; border: none; padding: 10px 20px;
      border-radius: 4px; cursor: pointer; font-size: 14px; transition: all 0.2s;
    }
    .controls button:hover { background-color: #1e53e5; transform: translateY(-1px); }
    .controls button.sample { background-color: #ff9800; }
    .controls button.danger { background-color: #f44336; }
    .status {
      display: inline-block; padding: 6px 12px; border-radius: 20px;
      font-size: 0.9rem; font-weight: 500; margin-left: 10px;
    }
    .status.loading { background-color: #363a45; color: #787b86; }
    .status.success { background-color: #26a69a; color: #ffffff; }
    .status.error { background-color: #ef5350; color: #ffffff; }
    .info-panel {
      display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
      gap: 20px; margin-top: 20px;
    }
    .info-card {
      background-color: #1e222d; border-radius: 8px; padding: 20px;
      box-shadow: 0 2px 8px rgba(0, 0, 0, 0.2); transition: transform 0.2s;
    }
    .info-card:hover { transform: translateY(-2px); }
    .info-card h3 { color: #ffffff; font-size: 1.2rem; margin-bottom: 15px; }
    .info-card p {
      color: #b2b5be; margin-bottom: 8px; display: flex; justify-content: space-between;
    }
    .info-value { color: #ffffff; font-weight: 500; }
    .loading-overlay {
      position: fixed; top: 0; left: 0; right: 0; bottom: 0;
      background-color: rgba(19, 23, 34, 0.9); display: none;
      align-items: center; justify-content: center; z-index: 1000;
    }
    .loading-spinner {
      border: 3px solid #363a45; border-top: 3px solid #2962ff; border-radius: 50%;
      width: 40px; height: 40px; animation: spin 1s linear infinite; margin: 0 auto 20px;
    }
    @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
    .connection-indicator {
      width: 10px; height: 10px; border-radius: 50%; display: inline-block; margin-right: 5px;
    }
    .connected { background-color: #26a69a; animation: pulse 2s infinite; }
    .disconnected { background-color: #ef5350; }
    @keyframes pulse {
      0% { box-shadow: 0 0 0 0 rgba(38, 166, 154, 0.7); }
      70% { box-shadow: 0 0 0 10px rgba(38, 166, 154, 0); }
      100% { box-shadow: 0 0 0 0 rgba(38, 166, 154, 0); }
    }
    .error-message {
      background-color: #ef5350; color: white; padding: 15px; border-radius: 4px;
      margin-bottom: 20px; display: none;
    }
    .chart-wrapper { position: relative; }
    .auto-refresh {
      display: flex; align-items: center; gap: 10px; margin-left: auto;
    }
    .auto-refresh input[type="checkbox"] { width: 18px; height: 18px; cursor: pointer; }
    .auto-refresh label { color: #b2b5be; cursor: pointer; }
  </style>
</head>
<body>
  <div class="container">
    <div class="header">
      <h1>🖥️ Ubuntu Server Renko Chart</h1>
      <p>Real-time Renko chart hosted on Ubuntu with Flask + ATR-based brick size</p>
    </div>

    <div class="server-info">
      <strong>🚀 Ubuntu Server Active!</strong> 
      Server: <code>{{ server_ip }}:{{ server_port }}</code> | 
      Uptime: <span id="uptime">{{ uptime }}</span> |
      Requests: <span id="request-count">{{ requests }}</span>
    </div>

    <div id="error-message" class="error-message"></div>

    <div class="controls">
      <button onclick="refreshData()" id="refresh-btn">🔄 Refresh Data</button>
      <button onclick="loadSampleData()" class="sample">📊 Sample Data</button>
      <button onclick="forceRefresh()" class="danger">⚡ Force Refresh</button>
      <button onclick="downloadData()">💾 Download JSON</button>
      <span id="status" class="status loading">Initializing...</span>
      
      <div class="auto-refresh">
        <input type="checkbox" id="auto-refresh" onchange="toggleAutoRefresh()">
        <label for="auto-refresh">Auto-refresh (30s)</label>
      </div>
    </div>

    <div class="chart-container">
      <div class="chart-wrapper">
        <div id="chart"></div>
      </div>
    </div>

    <div class="info-panel">
      <div class="info-card">
        <h3>📊 Chart Statistics</h3>
        <p><strong>Total Bars:</strong> <span class="info-value" id="total-bars">-</span></p>
        <p><strong>Price Range:</strong> <span class="info-value" id="price-range">-</span></p>
        <p><strong>Trend:</strong> <span class="info-value" id="trend">-</span></p>
        <p><strong>Last Update:</strong> <span class="info-value" id="last-update">-</span></p>
      </div>
      
      <div class="info-card">
        <h3>🖥️ Server Status</h3>
        <p><strong>Platform:</strong> <span class="info-value">Ubuntu Server</span></p>
        <p><strong>Status:</strong> <span class="info-value"><span id="connection-indicator" class="connection-indicator disconnected"></span><span id="api-status">Connecting...</span></span></p>
        <p><strong>Response Time:</strong> <span class="info-value" id="response-time">-</span></p>
        <p><strong>Data Source:</strong> <span class="info-value" id="data-source">Flask API</span></p>
      </div>

      <div class="info-card">
        <h3>📈 Latest Values</h3>
        <p><strong>Last Close:</strong> <span class="info-value" id="last-close">-</span></p>
        <p><strong>Last High:</strong> <span class="info-value" id="last-high">-</span></p>
        <p><strong>Last Low:</strong> <span class="info-value" id="last-low">-</span></p>
        <p><strong>Change:</strong> <span class="info-value" id="change">-</span></p>
      </div>

      <div class="info-card">
        <h3>⚙️ System Info</h3>
        <p><strong>Server IP:</strong> <span class="info-value">{{ server_ip }}</span></p>
        <p><strong>Port:</strong> <span class="info-value">{{ server_port }}</span></p>
        <p><strong>Python:</strong> <span class="info-value">{{ python_version }}</span></p>
        <p><strong>OS:</strong> <span class="info-value">{{ os_info }}</span></p>
      </div>
    </div>
  </div>

  <div id="loading" class="loading-overlay">
    <div class="loading-content">
      <div class="loading-spinner"></div>
      <p style="color: #b2b5be;">Loading Renko data...</p>
    </div>
  </div>

  <script>
    let chart = null;
    let renkoSeries = null;
    let currentData = null;
    let autoRefreshInterval = null;
    
    const API_ENDPOINT = '/api/renko-data';
    const AUTO_REFRESH_INTERVAL = 30000;
    
    function initChart() {
      try {
        const chartElement = document.getElementById('chart');
        if (typeof LightweightCharts === 'undefined') {
          throw new Error('Chart library not loaded');
        }

        chart = LightweightCharts.createChart(chartElement, {
          width: chartElement.clientWidth, height: 600,
          layout: { background: { color: '#1e222d' }, textColor: '#d1d4dc' },
          grid: { vertLines: { color: '#2a2e39' }, horzLines: { color: '#2a2e39' } },
          timeScale: { timeVisible: true, borderColor: '#2a2e39' },
          rightPriceScale: { borderColor: '#2a2e39' }
        });

        renkoSeries = chart.addCandlestickSeries({
          upColor: '#26a69a', downColor: '#ef5350',
          borderUpColor: '#26a69a', borderDownColor: '#ef5350',
          wickUpColor: '#26a69a', wickDownColor: '#ef5350'
        });

        window.addEventListener('resize', () => {
          chart.applyOptions({ width: chartElement.clientWidth });
        });

        updateStatus('success', 'Chart ready');
        return true;
      } catch (error) {
        console.error('Chart init failed:', error);
        updateStatus('error', 'Init failed');
        return false;
      }
    }

    async function loadRenkoData() {
      const startTime = Date.now();
      try {
        showLoading(true);
        updateStatus('loading', 'Fetching data...');
        
        const response = await fetch(API_ENDPOINT + '?t=' + Date.now());
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        
        const result = await response.json();
        const responseTime = Date.now() - startTime;
        
        if (!result.renko || !Array.isArray(result.renko)) {
          throw new Error('Invalid data format');
        }

        const renkoData = result.renko.map((bar, index) => {
          let timestamp;
          try {
            timestamp = new Date(bar.date).getTime() / 1000;
            if (isNaN(timestamp)) timestamp = Date.now() / 1000 - ((result.renko.length - index) * 60);
          } catch {
            timestamp = Date.now() / 1000 - ((result.renko.length - index) * 60);
          }
          
          return {
            time: Math.floor(timestamp + index * 60),
            open: parseFloat(bar.open) || 0,
            high: parseFloat(bar.high) || 0,
            low: parseFloat(bar.low) || 0,
            close: parseFloat(bar.close) || 0
          };
        });

        const validData = renkoData.filter(bar => 
          !isNaN(bar.time) && bar.open > 0 && bar.high > 0 && bar.low > 0 && bar.close > 0
        );

        if (validData.length === 0) throw new Error('No valid data');
        
        validData.sort((a, b) => a.time - b.time);
        renkoSeries.setData(validData);
        currentData = validData;
        
        setTimeout(() => chart.timeScale().fitContent(), 100);
        
        updateStatistics(validData);
        document.getElementById('api-status').textContent = 'Connected';
        document.getElementById('connection-indicator').className = 'connection-indicator connected';
        document.getElementById('response-time').textContent = responseTime + 'ms';
        document.getElementById('last-update').textContent = new Date().toLocaleTimeString();
        document.getElementById('data-source').textContent = result.source || 'Flask API';
        updateStatus('success', `Loaded ${validData.length} bars`);
        hideError();
        
        // Update request counter
        if (result.stats) {
          document.getElementById('request-count').textContent = result.stats.requests_served;
        }
        
      } catch (error) {
        console.error('Load failed:', error);
        showError(`Server Error: ${error.message}`);
        updateStatus('error', 'Load failed');
        document.getElementById('api-status').textContent = 'Error';
        loadSampleData();
      } finally {
        showLoading(false);
      }
    }

    function loadSampleData() {
      try {
        showLoading(true);
        updateStatus('loading', 'Generating sample data...');
        
        const sampleData = [];
        const baseTime = Math.floor(Date.now() / 1000) - (100 * 3600);
        let price = 2650;
        
        for (let i = 0; i < 100; i++) {
          const direction = Math.random() > 0.48 ? 1 : -1;
          const brickSize = 25 + (Math.random() * 15);
          const open = price;
          const close = open + (brickSize * direction);
          
          sampleData.push({
            time: baseTime + (i * 3600),
            open: Math.round(open * 100) / 100,
            high: Math.round((Math.max(open, close) + Math.random() * 5) * 100) / 100,
            low: Math.round((Math.min(open, close) - Math.random() * 5) * 100) / 100,
            close: Math.round(close * 100) / 100
          });
          
          price = close;
        }
        
        renkoSeries.setData(sampleData);
        currentData = sampleData;
        setTimeout(() => chart.timeScale().fitContent(), 100);
        
        updateStatistics(sampleData);
        document.getElementById('api-status').textContent = 'Sample Data';
        document.getElementById('connection-indicator').className = 'connection-indicator connected';
        document.getElementById('data-source').textContent = 'Sample Generator';
        updateStatus('success', `Generated ${sampleData.length} sample bars`);
        hideError();
        
      } catch (e) {
        console.error('Sample data failed:', e);
        updateStatus('error', 'Sample failed');
      } finally {
        showLoading(false);
      }
    }

    function forceRefresh() {
      fetch('/api/refresh', { method: 'POST' })
        .then(() => {
          setTimeout(loadRenkoData, 1000);
        })
        .catch(console.error);
    }

    function downloadData() {
      if (currentData) {
        const dataStr = JSON.stringify(currentData, null, 2);
        const dataBlob = new Blob([dataStr], {type: 'application/json'});
        const url = URL.createObjectURL(dataBlob);
        const link = document.createElement('a');
        link.href = url;
        link.download = 'renko-data-' + new Date().toISOString().slice(0,10) + '.json';
        link.click();
        URL.revokeObjectURL(url);
      }
    }

    function updateStatistics(data) {
      if (!data || data.length === 0) return;
      
      const lastBar = data[data.length - 1];
      const firstBar = data[0];
      const prices = data.flatMap(d => [d.high, d.low]);
      const minPrice = Math.min(...prices);
      const maxPrice = Math.max(...prices);
      const change = lastBar.close - firstBar.open;
      const changePercent = ((change / firstBar.open) * 100).toFixed(2);
      
      let upBars = 0, downBars = 0;
      data.forEach(bar => {
        if (bar.close > bar.open) upBars++;
        else if (bar.close < bar.open) downBars++;
      });
      
      document.getElementById('total-bars').textContent = data.length;
      document.getElementById('price-range').textContent = `${minPrice.toFixed(2)} - ${maxPrice.toFixed(2)}`;
      document.getElementById('last-close').textContent = lastBar.close.toFixed(2);
      document.getElementById('last-high').textContent = lastBar.high.toFixed(2);
      document.getElementById('last-low').textContent = lastBar.low.toFixed(2);
      document.getElementById('trend').textContent = upBars > downBars ? 'Bullish ↗' : 'Bearish ↘';
      document.getElementById('change').innerHTML = `<span style="color: ${change >= 0 ? '#26a69a' : '#ef5350'}">${change >= 0 ? '+' : ''}${change.toFixed(2)} (${changePercent}%)</span>`;
    }

    function updateStatus(type, message) {
      const statusElement = document.getElementById('status');
      statusElement.className = `status ${type}`;
      statusElement.textContent = message;
    }

    function showLoading(show) {
      document.getElementById('loading').style.display = show ? 'flex' : 'none';
    }

    function showError(message) {
      const errorElement = document.getElementById('error-message');
      errorElement.textContent = message;
      errorElement.style.display = 'block';
    }

    function hideError() {
      document.getElementById('error-message').style.display = 'none';
    }

    function refreshData() {
      loadRenkoData();
    }

    function toggleAutoRefresh() {
      const checkbox = document.getElementById('auto-refresh');
      if (checkbox.checked) {
        autoRefreshInterval = setInterval(loadRenkoData, AUTO_REFRESH_INTERVAL);
      } else {
        if (autoRefreshInterval) {
          clearInterval(autoRefreshInterval);
          autoRefreshInterval = null;
        }
      }
    }

    // Update uptime counter
    function updateUptime() {
      fetch('/api/stats')
        .then(response => response.json())
        .then(data => {
          document.getElementById('uptime').textContent = data.uptime;
          document.getElementById('request-count').textContent = data.requests_served;
        })
        .catch(() => {});
    }

    // Initialize
    document.addEventListener('DOMContentLoaded', () => {
      if (initChart()) {
        loadRenkoData();
        setInterval(updateUptime, 10000); // Update every 10 seconds
      }
    });
  </script>
</body>
</html>
'''

def get_server_ip():
    """Get server IP address"""
    try:
        # Connect to a remote server to determine local IP
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return "localhost"

def generate_renko_data():
    """Generate enhanced Renko data"""
    global renko_df
    
    try:
        # Try to load from actual data files first
        input_folder = 'data/tick/'
        output_folder = 'data/output/ohcl/'
        filename = 'SPY_2025_W21'
        
        tick_file_path = f'{input_folder}{filename}.parquet'
        if os.path.exists(tick_file_path):
            logger.info(f"Loading tick data from: {tick_file_path}")
            tick_df = pd.read_parquet(tick_file_path, engine='pyarrow')
            
            # Process to OHLC
            ohcl_df = tick_df.resample('1min', closed='right', label='right').agg({
                'price': 'ohlc',
                'size': 'sum'
            })
            ohcl_df = ohcl_df.dropna()
            ohcl_df.columns = ['open', 'high', 'low', 'close', 'volume']
            ohcl_df = ohcl_df.reset_index().rename(columns={'timestamp': 'date'})
            ohcl_df.set_index('date', inplace=True)
            
            # Generate Renko chart
            retvals = {}
            try:
                import matplotlib
                matplotlib.use('Agg')
                import matplotlib.pyplot as plt
                plt.ioff()
                
                fig = mpf.plot(ohcl_df, type='renko', 
                             renko_params=dict(brick_size='atr', atr_length=14), 
                             style='yahoo', figsize=(180, 7), returnfig=True,
                             title=f"RENKO CHART WITH ATR {filename}", 
                             return_calculated_values=retvals)
                
                if fig and len(fig) > 0:
                    plt.close(fig[0])
                
                logger.info(f"Renko calculation completed. Keys: {list(retvals.keys())}")
                
            except Exception as e:
                logger.error(f"Error generating Renko chart: {e}")
                retvals = {
                    'renko_bricks': ohcl_df['close'].values[:100],
                    'renko_dates': ohcl_df.index[:100],
                    'renko_size': [2.0] * 100
                }
        else:
            logger.info("No tick data found, generating enhanced sample data")
            # Enhanced sample data generation
            sample_dates = pd.date_range('2025-01-01', periods=150, freq='1H')
            base_price = 450.0
            
            prices = []
            for i in range(150):
                # More realistic price movements
                trend = 0.1 if i < 75 else -0.05  # Bull then bear market
                volatility = 0.02 + (i % 10) * 0.001
                noise = (np.random.random() - 0.5) * volatility * base_price
                base_price += trend + noise
                prices.append(max(base_price, 100))  # Prevent negative prices
            
            retvals = {
                'renko_bricks': prices,
                'renko_dates': sample_dates,
                'renko_size': [2.0] * 150
            }
        
        # Convert to DataFrame
        renko_df = pd.DataFrame(retvals)
        
        # Calculate OHLC for Renko bricks
        renko_df = renko_df.copy()
        renko_df['open'] = renko_df['renko_bricks'].shift(1)
        
        if len(renko_df) > 0:
            renko_df.loc[renko_df.index[0], 'open'] = (
                renko_df.loc[renko_df.index[0], 'renko_bricks'] - 
                renko_df.loc[renko_df.index[0], 'renko_size']
            )
        
        renko_df['high'] = renko_df[['open', 'renko_bricks']].max(axis=1) + (renko_df['renko_size'] * 0.1)
        renko_df['low'] = renko_df[['open', 'renko_bricks']].min(axis=1) - (renko_df['renko_size'] * 0.1)
        renko_df['close'] = renko_df['renko_bricks']
        
        server_stats['data_refreshes'] += 1
        logger.info(f"Generated {len(renko_df)} Renko bars")
        return renko_df
        
    except Exception as e:
        logger.error(f"Error in generate_renko_data: {e}")
        server_stats['errors'] += 1
        
        # Fallback data
        sample_dates = pd.date_range('2025-01-01', periods=50, freq='1H')
        return pd.DataFrame({
            'renko_dates': sample_dates,
            'renko_bricks': [450 + i * 2 for i in range(50)],
            'renko_size': [2.0] * 50,
            'open': [448 + i * 2 for i in range(50)],
            'high': [452 + i * 2 for i in range(50)],
            'low': [448 + i * 2 for i in range(50)],
            'close': [450 + i * 2 for i in range(50)]
        })

@app.route('/')
def index():
    """Serve the main interface with server info"""
    try:
        server_ip = get_server_ip()
        uptime = str(datetime.now() - server_stats['start_time']).split('.')[0]
        
        return render_template_string(HTML_TEMPLATE, 
            server_ip=server_ip,
            server_port=8000,
            uptime=uptime,
            requests=server_stats['requests_served'],
            python_version=f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
            os_info=f"{os.uname().sysname} {os.uname().release}"
        )
    except Exception as e:
        logger.error(f"Error serving index: {e}")
        return f"Server Error: {e}", 500

@app.route('/api/renko-data', methods=['GET'])
def get_renko_data():
    """Enhanced API endpoint with server stats"""
    try:
        start_time = time.time()
        server_stats['requests_served'] += 1
        
        global renko_df
        if renko_df is None:
            renko_df = generate_renko_data()
        
        # Convert DataFrame to JSON
        renko_data = []
        for idx_pos, (idx, row) in enumerate(renko_df.iterrows()):
            if 'renko_dates' in renko_df.columns:
                timestamp = row['renko_dates']
            else:
                timestamp = pd.Timestamp('2025-01-01') + pd.Timedelta(hours=idx_pos)
            
            try:
                date_iso = timestamp.isoformat() if hasattr(timestamp, 'isoformat') else pd.to_datetime(timestamp).isoformat()
            except:
                date_iso = (pd.Timestamp('2025-01-01') + pd.Timedelta(hours=idx_pos)).isoformat()
            
            renko_data.append({
                'date': date_iso,
                'open': float(row['open']),
                'high': float(row['high']),
                'low': float(row['low']),
                'close': float(row['close'])
            })
        
        processing_time = time.time() - start_time
        
        response = {
            'renko': renko_data,
            'source': 'Ubuntu Flask Server',
            'stats': {
                'requests_served': server_stats['requests_served'],
                'data_refreshes': server_stats['data_refreshes'],
                'processing_time': round(processing_time, 3),
                'data_points': len(renko_data),
                'server_uptime': str(datetime.now() - server_stats['start_time']).split('.')[0]
            }
        }
        
        logger.info(f"Served {len(renko_data)} bars in {processing_time:.3f}s")
        return jsonify(response)
        
    except Exception as e:
        logger.error(f"Error in get_renko_data: {e}")
        server_stats['errors'] += 1
        return jsonify({
            'renko': [],
            'error': str(e),
            'source': 'Ubuntu Flask Server'
        }), 500

@app.route('/api/refresh', methods=['POST'])
def force_refresh():
    """Force refresh the Renko data"""
    try:
        global renko_df
        renko_df = generate_renko_data()
        logger.info("Data force refreshed")
        return jsonify({
            'status': 'success',
            'message': 'Data refreshed',
            'data_points': len(renko_df) if renko_df is not None else 0
        })
    except Exception as e:
        logger.error(f"Error in force refresh: {e}")
        server_stats['errors'] += 1
        return jsonify({'error': str(e)}), 500

@app.route('/api/stats', methods=['GET'])
def get_stats():
    """Get server statistics"""
    try:
        uptime = datetime.now() - server_stats['start_time']
        return jsonify({
            'uptime': str(uptime).split('.')[0],
            'requests_served': server_stats['requests_served'],
            'data_refreshes': server_stats['data_refreshes'],
            'errors': server_stats['errors'],
            'server_ip': get_server_ip(),
            'python_version': f"{sys.version_info.major}.{sys.version_info.minor}",
            'data_points': len(renko_df) if renko_df is not None else 0,
            'memory_usage': f"{sys.getsizeof(renko_df) / 1024:.1f} KB" if renko_df is not None else "0 KB"
        })
    except Exception as e:
        logger.error(f"Error getting stats: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/health', methods=['GET'])
def health_check():
    """Comprehensive health check"""
    try:
        health_status = {
            'status': 'healthy',
            'timestamp': datetime.now().isoformat(),
            'server': {
                'platform': 'Ubuntu Server',
                'ip': get_server_ip(),
                'port': 8000,
                'uptime': str(datetime.now() - server_stats['start_time']).split('.')[0],
                'python_version': f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
            },
            'data': {
                'available': renko_df is not None,
                'points': len(renko_df) if renko_df is not None else 0,
                'last_refresh': server_stats['data_refreshes']
            },
            'stats': server_stats.copy()
        }
        
        # Check if data is available
        if renko_df is None or len(renko_df) == 0:
            health_status['status'] = 'degraded'
            health_status['warning'] = 'No data available'
        
        return jsonify(health_status)
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return jsonify({
            'status': 'unhealthy',
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500

def signal_handler(signum, frame):
    """Graceful shutdown handler"""
    logger.info(f"Received signal {signum}, shutting down gracefully...")
    logger.info(f"Final stats: {server_stats}")
    sys.exit(0)

if __name__ == '__main__':
    # Set up signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        # Import numpy for sample data generation
        import numpy as np
    except ImportError:
        logger.warning("NumPy not available, using basic random")
        import random
        np = type('MockNumPy', (), {'random': type('MockRandom', (), {'random': random.random})()})()
    
    logger.info("🖥️ Starting Ubuntu Renko Chart Server...")
    logger.info("=" * 60)
    
    # Generate initial data
    try:
        logger.info("Generating initial Renko data...")
        renko_df = generate_renko_data()
        logger.info(f"✅ Loaded {len(renko_df)} Renko bars")
    except Exception as e:
        logger.error(f"❌ Error during initialization: {e}")
    
    # Get server info
    server_ip = get_server_ip()
    
    print("\n" + "🚀 UBUNTU SERVER READY!" + "\n" + "=" * 60)
    print(f"📊 Main Interface: http://{server_ip}:8000")
    print(f"🔌 API Endpoint:   http://{server_ip}:8000/api/renko-data")
    print(f"💚 Health Check:   http://{server_ip}:8000/api/health")
    print(f"📈 Server Stats:   http://{server_ip}:8000/api/stats")
    print("=" * 60)
    print(f"🌐 Network Access: http://{server_ip}:8000 (from any device)")
    print(f"🏠 Local Access:   http://localhost:8000")
    print("=" * 60)
    print(f"📝 Logs:          /renko-chart.log")
    print(f"🔄 Auto-refresh:   Every 30 seconds (optional)")
    print(f"⚡ Force refresh:  POST /api/refresh")
    print("=" * 60 + "\n")
    
    # Start the server
    try:
        app.run(
            host='0.0.0.0',  # Accept connections from any IP
            port=8000,
            debug=False,     # Disable debug in production
            threaded=True,   # Handle multiple requests
            use_reloader=False  # Prevent double startup
        )
    except Exception as e:
        logger.error(f"Failed to start server: {e}")
        sys.exit(1)