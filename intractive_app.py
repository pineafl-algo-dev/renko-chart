#!/usr/bin/env python3
"""
Dynamic Renko Chart Server - User File Selection
Allows users to input filename and generate Renko charts from actual tick data
Run with: python3 dynamic_app.py
Access at: http://YOUR_SERVER_IP:5000
"""

from flask import Flask, jsonify, render_template_string, request
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
import glob
from pathlib import Path
import traceback

# Suppress pandas warnings
warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=UserWarning)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/renko-chart-dynamic.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app, origins=["*"])

# Global variables
renko_cache = {}  # Cache for different files
server_stats = {
    'start_time': datetime.now(),
    'requests_served': 0,
    'files_processed': 0,
    'errors': 0,
    'available_files': []
}

# Configuration
DATA_CONFIG = {
    'input_folder': 'data/tick/',
    'output_folder': 'data/output/ohcl/',
    'supported_formats': ['.parquet', '.csv', '.h5'],
    'renko_params': {
        'brick_size': 'atr',
        'atr_length': 14
    }
}

# HTML template with file selection
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Dynamic Renko Chart - File Selection</title>
  <script src="https://unpkg.com/lightweight-charts@4.1.3/dist/lightweight-charts.standalone.production.js"></script>
  <style>
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body {
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
      background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%);
      color: #ffffff; padding: 20px; min-height: 100vh;
    }
    .container { max-width: 1400px; margin: 0 auto; }
    .header { text-align: center; margin-bottom: 30px; }
    .header h1 { 
      color: #ffffff; font-size: 2.8rem; font-weight: 700; margin-bottom: 10px;
      text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
    }
    .header p { color: #e8f4f8; font-size: 1.2rem; }
    
    .file-selector {
      background: rgba(255,255,255,0.1); backdrop-filter: blur(10px);
      border-radius: 15px; padding: 25px; margin-bottom: 25px;
      border: 1px solid rgba(255,255,255,0.2); box-shadow: 0 8px 32px rgba(0,0,0,0.3);
    }
    .file-selector h3 { color: #ffffff; margin-bottom: 20px; font-size: 1.3rem; }
    
    .input-group {
      display: flex; gap: 15px; align-items: center; flex-wrap: wrap; margin-bottom: 20px;
    }
    .input-group input {
      flex: 1; min-width: 250px; padding: 12px 15px; border-radius: 8px;
      border: 1px solid rgba(255,255,255,0.3); background: rgba(255,255,255,0.1);
      color: #ffffff; font-size: 16px; backdrop-filter: blur(5px);
    }
    .input-group input::placeholder { color: rgba(255,255,255,0.7); }
    .input-group input:focus {
      outline: none; border-color: #4fc3f7; box-shadow: 0 0 0 3px rgba(79,195,247,0.3);
    }
    
    .btn {
      padding: 12px 24px; border-radius: 8px; border: none; cursor: pointer;
      font-size: 14px; font-weight: 600; transition: all 0.3s;
      text-transform: uppercase; letter-spacing: 0.5px;
    }
    .btn-primary { background: #4fc3f7; color: #ffffff; }
    .btn-primary:hover { background: #29b6f6; transform: translateY(-2px); }
    .btn-success { background: #66bb6a; color: #ffffff; }
    .btn-success:hover { background: #4caf50; transform: translateY(-2px); }
    .btn-warning { background: #ffa726; color: #ffffff; }
    .btn-warning:hover { background: #ff9800; transform: translateY(-2px); }
    
    .available-files {
      background: rgba(255,255,255,0.05); padding: 15px; border-radius: 8px;
      margin-top: 15px; max-height: 150px; overflow-y: auto;
    }
    .file-item {
      padding: 8px 12px; margin: 3px 0; background: rgba(255,255,255,0.1);
      border-radius: 5px; cursor: pointer; transition: background 0.2s;
      font-family: monospace; font-size: 13px;
    }
    .file-item:hover { background: rgba(255,255,255,0.2); }
    
    .chart-container {
      background: rgba(255,255,255,0.1); backdrop-filter: blur(10px);
      border-radius: 15px; padding: 25px; margin-bottom: 25px;
      border: 1px solid rgba(255,255,255,0.2); box-shadow: 0 8px 32px rgba(0,0,0,0.3);
      position: relative;
    }
    #chart { width: 100%; height: 600px; border-radius: 10px; background: #1e222d; }
    
    .chart-toolbar {
      position: absolute; top: 35px; right: 35px; display: flex; gap: 8px;
      z-index: 1000; background: rgba(30, 34, 45, 0.95); padding: 8px;
      border-radius: 8px; backdrop-filter: blur(10px);
      border: 1px solid rgba(255,255,255,0.1);
    }
    .chart-toolbar button {
      background: rgba(255,255,255,0.1); color: #d1d4dc; border: none;
      padding: 8px 10px; cursor: pointer; border-radius: 5px; font-size: 14px;
      transition: all 0.2s; min-width: 32px; height: 32px;
      display: flex; align-items: center; justify-content: center;
    }
    .chart-toolbar button:hover {
      background: #4fc3f7; color: #ffffff; transform: translateY(-1px);
    }
    .chart-toolbar button:active { transform: translateY(0px); }
    
    .timeframe-controls {
      position: absolute; top: 35px; left: 35px; display: flex; gap: 5px;
      z-index: 1000; background: rgba(30, 34, 45, 0.95); padding: 8px;
      border-radius: 8px; backdrop-filter: blur(10px);
      border: 1px solid rgba(255,255,255,0.1);
    }
    .timeframe-controls button {
      background: rgba(255,255,255,0.1); color: #d1d4dc; border: none;
      padding: 6px 12px; cursor: pointer; border-radius: 4px; font-size: 12px;
      transition: all 0.2s; font-weight: 600;
    }
    .timeframe-controls button:hover {
      background: #4fc3f7; color: #ffffff;
    }
    .timeframe-controls button.active {
      background: #4fc3f7; color: #ffffff; box-shadow: 0 2px 8px rgba(79,195,247,0.3);
    }
    
    .chart-info-overlay {
      position: absolute; top: 80px; left: 35px; background: rgba(30, 34, 45, 0.95);
      padding: 12px 16px; border-radius: 8px; font-size: 12px; z-index: 1000;
      backdrop-filter: blur(10px); border: 1px solid rgba(255,255,255,0.1);
      display: none; min-width: 200px;
    }
    .chart-info-overlay.visible { display: block; }
    .chart-info-overlay div {
      margin-bottom: 4px; color: #b2b5be; display: flex; justify-content: space-between;
    }
    .chart-info-overlay .price {
      color: #4fc3f7; font-size: 14px; font-weight: bold; margin-bottom: 8px;
    }
    .chart-info-overlay .ohlc-data {
      display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-top: 8px;
    }
    
    .volume-indicator {
      position: absolute; bottom: 80px; left: 35px; background: rgba(30, 34, 45, 0.95);
      padding: 8px 12px; border-radius: 6px; font-size: 11px; z-index: 1000;
      backdrop-filter: blur(10px); border: 1px solid rgba(255,255,255,0.1);
      color: #b2b5be;
    }
    
    .crosshair-toggle {
      position: absolute; bottom: 35px; right: 35px; z-index: 1000;
    }
    .crosshair-toggle button {
      background: rgba(30, 34, 45, 0.95); color: #d1d4dc; border: none;
      padding: 8px 12px; cursor: pointer; border-radius: 6px; font-size: 12px;
      backdrop-filter: blur(10px); border: 1px solid rgba(255,255,255,0.1);
      transition: all 0.2s;
    }
    .crosshair-toggle button:hover { background: #4fc3f7; color: #ffffff; }
    .crosshair-toggle button.active { background: #4fc3f7; color: #ffffff; }
    
    .controls {
      background: rgba(255,255,255,0.1); backdrop-filter: blur(10px);
      border-radius: 15px; padding: 20px; margin-bottom: 20px;
      display: flex; align-items: center; gap: 15px; flex-wrap: wrap;
      border: 1px solid rgba(255,255,255,0.2);
    }
    
    .info-panel {
      display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
      gap: 20px; margin-top: 20px;
    }
    .info-card {
      background: rgba(255,255,255,0.1); backdrop-filter: blur(10px);
      border-radius: 15px; padding: 25px; border: 1px solid rgba(255,255,255,0.2);
      box-shadow: 0 8px 32px rgba(0,0,0,0.3); transition: transform 0.3s;
    }
    .info-card:hover { transform: translateY(-5px); }
    .info-card h3 { color: #ffffff; font-size: 1.2rem; margin-bottom: 15px; }
    .info-card p {
      color: rgba(255,255,255,0.8); margin-bottom: 8px;
      display: flex; justify-content: space-between; align-items: center;
    }
    .info-value { color: #4fc3f7; font-weight: 600; }
    
    .status {
      display: inline-block; padding: 6px 14px; border-radius: 20px;
      font-size: 0.9rem; font-weight: 600; margin-left: 10px;
    }
    .status.loading { background: rgba(255,193,7,0.2); color: #ffc107; }
    .status.success { background: rgba(76,175,80,0.2); color: #4caf50; }
    .status.error { background: rgba(244,67,54,0.2); color: #f44336; }
    
    .loading-overlay {
      position: fixed; top: 0; left: 0; right: 0; bottom: 0;
      background: rgba(0,0,0,0.8); backdrop-filter: blur(5px);
      display: none; align-items: center; justify-content: center; z-index: 1000;
    }
    .loading-spinner {
      border: 4px solid rgba(255,255,255,0.3); border-top: 4px solid #4fc3f7;
      border-radius: 50%; width: 50px; height: 50px; animation: spin 1s linear infinite;
    }
    @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
    
    .error-message, .success-message {
      padding: 15px 20px; border-radius: 10px; margin-bottom: 20px;
      font-weight: 500; text-align: center;
    }
    .error-message { background: rgba(244,67,54,0.2); border: 1px solid #f44336; color: #ffffff; }
    .success-message { background: rgba(76,175,80,0.2); border: 1px solid #4caf50; color: #ffffff; }
    .error-message { display: none; }
    
    .connection-indicator {
      width: 10px; height: 10px; border-radius: 50%; display: inline-block; margin-right: 8px;
    }
    .connected { background: #4caf50; animation: pulse 2s infinite; }
    .disconnected { background: #f44336; }
    @keyframes pulse {
      0% { box-shadow: 0 0 0 0 rgba(76,175,80,0.7); }
      70% { box-shadow: 0 0 0 10px rgba(76,175,80,0); }
      100% { box-shadow: 0 0 0 0 rgba(76,175,80,0); }
    }
    
    .file-stats {
      display: grid; grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
      gap: 10px; margin-top: 15px;
    }
    .stat-item {
      background: rgba(255,255,255,0.1); padding: 10px; border-radius: 8px; text-align: center;
    }
    .stat-value { font-size: 1.5rem; font-weight: bold; color: #4fc3f7; }
    .stat-label { font-size: 0.8rem; color: rgba(255,255,255,0.7); }
  </style>
</head>
<body>
  <div class="container">
    <div class="header">
      <h1>📊 Dynamic Renko Chart</h1>
      <p>Load any tick data file and generate real-time Renko charts with ATR-based brick sizing</p>
    </div>

    <div class="file-selector">
      <h3>📁 Select Tick Data File</h3>
      <div class="input-group">
        <input type="text" id="filename-input" placeholder="Enter filename (e.g., SPY_2025_W26)" 
               value="SPY_2025_W26" onkeypress="handleEnterKey(event)">
        <button class="btn btn-primary" onclick="loadFile()">🚀 Load & Generate Renko</button>
        <button class="btn btn-success" onclick="refreshFileList()">🔄 Refresh Files</button>
        <button class="btn btn-warning" onclick="loadSampleData()">📊 Sample Data</button>
      </div>
      
      <div class="available-files">
        <strong>📂 Available Files in {{ data_folder }}:</strong>
        <div id="file-list">Loading...</div>
      </div>
    </div>

    <div id="error-message" class="error-message"></div>
    <div id="success-message" class="success-message" style="display: none;"></div>

    <div class="controls">
      <span id="status" class="status loading">Ready to load data...</span>
      <button class="btn btn-primary" onclick="refreshData()">🔄 Refresh Current</button>
      <button class="btn btn-warning" onclick="downloadData()">💾 Download JSON</button>
    </div>

    <div class="chart-container">
      <div id="chart"></div>
      
      <!-- Chart Toolbar -->
      <div class="chart-toolbar">
        <button onclick="zoomIn()" title="Zoom In (I)" id="zoom-in-btn">🔍+</button>
        <button onclick="zoomOut()" title="Zoom Out (O)" id="zoom-out-btn">🔍-</button>
        <button onclick="resetZoom()" title="Reset Zoom (R)" id="reset-zoom-btn">⟲</button>
        <button onclick="fitContent()" title="Fit Content (F)" id="fit-content-btn">⤢</button>
        <button onclick="scrollLeft()" title="Scroll Left (←)" id="scroll-left-btn">←</button>
        <button onclick="scrollRight()" title="Scroll Right (→)" id="scroll-right-btn">→</button>
        <button onclick="scrollToEnd()" title="Go to Latest (End)" id="scroll-end-btn">⟫</button>
        <button onclick="scrollToStart()" title="Go to Start (Home)" id="scroll-start-btn">⟪</button>
      </div>
      
      <!-- Timeframe Controls -->
      <div class="timeframe-controls">
        <button onclick="showBars(50)" data-bars="50">50</button>
        <button onclick="showBars(100)" data-bars="100">100</button>
        <button onclick="showBars(200)" data-bars="200">200</button>
        <button onclick="showBars(500)" data-bars="500">500</button>
        <button onclick="showBars(1000)" data-bars="1000">1K</button>
        <button onclick="showBars(0)" data-bars="0" class="active">All</button>
      </div>
      
      <!-- Chart Info Overlay -->
      <div id="chart-info" class="chart-info-overlay">
        <div class="price">Price: <span id="hover-price">-</span></div>
        <div>Time: <span id="hover-time">-</span></div>
        <div class="ohlc-data">
          <div>O: <span id="hover-open">-</span></div>
          <div>H: <span id="hover-high">-</span></div>
          <div>L: <span id="hover-low">-</span></div>
          <div>C: <span id="hover-close">-</span></div>
        </div>
        <div style="margin-top: 8px; border-top: 1px solid rgba(255,255,255,0.1); padding-top: 4px;">
          <div>Change: <span id="hover-change">-</span></div>
          <div>% Change: <span id="hover-percent">-</span></div>
        </div>
      </div>
      
      <!-- Volume Indicator -->
      <div class="volume-indicator">
        <div>Bars Visible: <span id="visible-bars">-</span></div>
        <div>Total Bars: <span id="total-bars-indicator">-</span></div>
      </div>
      
      <!-- Crosshair Toggle -->
      <div class="crosshair-toggle">
        <button onclick="toggleCrosshair()" id="crosshair-btn" class="active">✚ Crosshair</button>
      </div>
    </div>

    <div class="info-panel">
      <div class="info-card">
        <h3>📈 Current File Statistics</h3>
        <p><strong>File Name:</strong> <span class="info-value" id="current-file">None</span></p>
        <p><strong>Total Bars:</strong> <span class="info-value" id="total-bars">-</span></p>
        <p><strong>Price Range:</strong> <span class="info-value" id="price-range">-</span></p>
        <p><strong>Data Points:</strong> <span class="info-value" id="data-points">-</span></p>
        <div class="file-stats">
          <div class="stat-item">
            <div class="stat-value" id="brick-count">-</div>
            <div class="stat-label">Renko Bricks</div>
          </div>
          <div class="stat-item">
            <div class="stat-value" id="timespan">-</div>
            <div class="stat-label">Time Span</div>
          </div>
        </div>
      </div>
      
      <div class="info-card">
        <h3>🖥️ Server Information</h3>
        <p><strong>Status:</strong> <span class="info-value"><span id="connection-indicator" class="connection-indicator disconnected"></span><span id="api-status">Connecting...</span></span></p>
        <p><strong>Files Processed:</strong> <span class="info-value" id="files-processed">{{ files_processed }}</span></p>
        <p><strong>Data Folder:</strong> <span class="info-value">{{ data_folder }}</span></p>
        <p><strong>Last Update:</strong> <span class="info-value" id="last-update">-</span></p>
      </div>

      <div class="info-card">
        <h3>📊 Chart Details</h3>
        <p><strong>Brick Type:</strong> <span class="info-value">ATR-based</span></p>
        <p><strong>ATR Length:</strong> <span class="info-value">14 periods</span></p>
        <p><strong>Current Trend:</strong> <span class="info-value" id="trend">-</span></p>
        <p><strong>Last Close:</strong> <span class="info-value" id="last-close">-</span></p>
      </div>

      <div class="info-card">
        <h3>⚙️ System Status</h3>
        <p><strong>Server IP:</strong> <span class="info-value">{{ server_ip }}</span></p>
        <p><strong>Uptime:</strong> <span class="info-value" id="uptime">{{ uptime }}</span></p>
        <p><strong>Total Requests:</strong> <span class="info-value" id="request-count">{{ requests }}</span></p>
        <p><strong>Processing Time:</strong> <span class="info-value" id="processing-time">-</span></p>
      </div>
    </div>
  </div>

  <div id="loading" class="loading-overlay">
    <div style="text-align: center; color: white;">
      <div class="loading-spinner"></div>
      <p style="margin-top: 20px; font-size: 1.1rem;">Processing tick data and generating Renko chart...</p>
      <p style="margin-top: 10px; color: #4fc3f7;">This may take a few moments for large files</p>
    </div>
  </div>

  <script>
    let chart = null;
    let renkoSeries = null;
    let currentData = null;
    let currentFile = null;
    let crosshairEnabled = true;
    let visibleLogicalRange = null;
    let chartReady = false;
    
    const API_BASE = '/api';
    
    function initChart() {
      try {
        const chartElement = document.getElementById('chart');
        if (typeof LightweightCharts === 'undefined') {
          throw new Error('Chart library not loaded');
        }

        chart = LightweightCharts.createChart(chartElement, {
          width: chartElement.clientWidth, 
          height: 600,
          layout: { 
            background: { color: '#1e222d' }, 
            textColor: '#d1d4dc',
            fontSize: 12
          },
          grid: { 
            vertLines: { color: '#2a2e39', style: 1, visible: true }, 
            horzLines: { color: '#2a2e39', style: 1, visible: true } 
          },
          crosshair: {
            mode: LightweightCharts.CrosshairMode.Normal,
            vertLine: {
              color: '#4fc3f7',
              width: 1,
              style: LightweightCharts.LineStyle.Dashed,
              labelBackgroundColor: '#4fc3f7',
            },
            horzLine: {
              color: '#4fc3f7',
              width: 1,
              style: LightweightCharts.LineStyle.Dashed,
              labelBackgroundColor: '#4fc3f7',
            },
          },
          timeScale: { 
            timeVisible: true, 
            secondsVisible: false,
            borderColor: '#2a2e39',
            rightOffset: 12,
            barSpacing: 6,
            fixLeftEdge: false,
            fixRightEdge: false,
            lockVisibleTimeRangeOnResize: true,
            rightBarStaysOnScroll: true,
            borderVisible: true,
            visible: true,
          },
          rightPriceScale: { 
            borderColor: '#2a2e39', 
            scaleMargins: { top: 0.1, bottom: 0.1 },
            borderVisible: true,
            entireTextOnly: false,
            visible: true,
            alignLabels: true,
            mode: LightweightCharts.PriceScaleMode.Normal,
          },
          leftPriceScale: {
            visible: false,
          },
          handleScroll: {
            mouseWheel: true,
            pressedMouseMove: true,
            horzTouchDrag: true,
            vertTouchDrag: true,
          },
          handleScale: {
            axisPressedMouseMove: {
              time: true,
              price: true,
            },
            mouseWheel: true,
            pinch: true,
          },
          kineticScroll: {
            mouse: false,
            touch: true,
          },
        });

        renkoSeries = chart.addCandlestickSeries({
          upColor: '#26a69a',
          downColor: '#ef5350',
          borderUpColor: '#26a69a',
          borderDownColor: '#ef5350',
          wickUpColor: '#26a69a',
          wickDownColor: '#ef5350',
          borderVisible: true,
          wickVisible: true,
          priceLineVisible: true,
          lastValueVisible: true,
          title: 'Renko Chart',
        });

        // Enhanced crosshair move handler
        chart.subscribeCrosshairMove((param) => {
          updateChartInfo(param);
          updateVisibleBarsCount();
        });

        // Subscribe to visible range changes
        chart.timeScale().subscribeVisibleLogicalRangeChange((newRange) => {
          visibleLogicalRange = newRange;
          updateVisibleBarsCount();
        });

        // Subscribe to chart click
        chart.subscribeClick((param) => {
          if (param.time && param.seriesPrices.has(renkoSeries)) {
            const data = param.seriesPrices.get(renkoSeries);
            console.log('Clicked bar:', {
              time: new Date(param.time * 1000).toLocaleString(),
              data: data
            });
          }
        });

        // Handle window resize
        window.addEventListener('resize', () => {
          chart.applyOptions({ width: chartElement.clientWidth });
        });

        // Mouse wheel zoom with Ctrl
        chartElement.addEventListener('wheel', (e) => {
          if (e.ctrlKey || e.metaKey) {
            e.preventDefault();
            if (e.deltaY < 0) {
              zoomIn();
            } else {
              zoomOut();
            }
          }
        }, { passive: false });

        chartReady = true;
        updateStatus('success', 'Interactive chart ready - select a file to load data');
        return true;
      } catch (error) {
        console.error('Chart init failed:', error);
        updateStatus('error', 'Chart initialization failed');
        return false;
      }
    }

    function updateChartInfo(param) {
      const infoOverlay = document.getElementById('chart-info');
      
      if (param.time && param.seriesPrices.has(renkoSeries) && crosshairEnabled) {
        const data = param.seriesPrices.get(renkoSeries);
        
        if (data) {
          const prevData = getPreviousBarData(param.time);
          const change = prevData ? data.close - prevData.close : 0;
          const percentChange = prevData ? ((change / prevData.close) * 100) : 0;
          
          document.getElementById('hover-price').textContent = `${data.close.toFixed(2)}`;
          document.getElementById('hover-open').textContent = data.open.toFixed(2);
          document.getElementById('hover-high').textContent = data.high.toFixed(2);
          document.getElementById('hover-low').textContent = data.low.toFixed(2);
          document.getElementById('hover-close').textContent = data.close.toFixed(2);
          
          const date = new Date(param.time * 1000);
          document.getElementById('hover-time').textContent = date.toLocaleString();
          
          document.getElementById('hover-change').textContent = `${change >= 0 ? '+' : ''}${change.toFixed(2)}`;
          document.getElementById('hover-change').style.color = change >= 0 ? '#26a69a' : '#ef5350';
          
          document.getElementById('hover-percent').textContent = `${percentChange >= 0 ? '+' : ''}${percentChange.toFixed(2)}%`;
          document.getElementById('hover-percent').style.color = percentChange >= 0 ? '#26a69a' : '#ef5350';
          
          infoOverlay.classList.add('visible');
        }
      } else {
        infoOverlay.classList.remove('visible');
      }
    }

    function getPreviousBarData(currentTime) {
      if (!currentData) return null;
      
      const currentIndex = currentData.findIndex(bar => bar.time === currentTime);
      if (currentIndex > 0) {
        return currentData[currentIndex - 1];
      }
      return null;
    }

    function updateVisibleBarsCount() {
      if (!chart || !currentData) return;
      
      const range = chart.timeScale().getVisibleLogicalRange();
      if (range) {
        const visibleBars = Math.round(range.to - range.from);
        document.getElementById('visible-bars').textContent = visibleBars;
      }
      
      if (currentData) {
        document.getElementById('total-bars-indicator').textContent = currentData.length;
      }
    }

    // Chart Control Functions
    function zoomIn() {
      if (!chart) return;
      
      const timeScale = chart.timeScale();
      const currentRange = timeScale.getVisibleLogicalRange();
      if (currentRange) {
        const barsCount = currentRange.to - currentRange.from;
        const newBarsCount = Math.max(5, Math.floor(barsCount * 0.7)); // Zoom in by 30%
        const center = (currentRange.from + currentRange.to) / 2;
        
        timeScale.setVisibleLogicalRange({
          from: center - newBarsCount / 2,
          to: center + newBarsCount / 2
        });
        
        // Visual feedback
        animateButton('zoom-in-btn');
      }
    }

    function zoomOut() {
      if (!chart) return;
      
      const timeScale = chart.timeScale();
      const currentRange = timeScale.getVisibleLogicalRange();
      if (currentRange) {
        const barsCount = currentRange.to - currentRange.from;
        const newBarsCount = Math.floor(barsCount * 1.4); // Zoom out by 40%
        const center = (currentRange.from + currentRange.to) / 2;
        
        timeScale.setVisibleLogicalRange({
          from: center - newBarsCount / 2,
          to: center + newBarsCount / 2
        });
        
        animateButton('zoom-out-btn');
      }
    }

    function resetZoom() {
      if (!chart) return;
      
      chart.timeScale().resetTimeScale();
      animateButton('reset-zoom-btn');
      console.log('Zoom reset');
    }

    function fitContent() {
      if (!chart) return;
      
      chart.timeScale().fitContent();
      animateButton('fit-content-btn');
      console.log('Content fitted');
    }

    function scrollLeft() {
      if (!chart) return;
      
      const timeScale = chart.timeScale();
      const currentRange = timeScale.getVisibleLogicalRange();
      if (currentRange) {
        const shift = (currentRange.to - currentRange.from) * 0.2; // Scroll by 20%
        timeScale.setVisibleLogicalRange({
          from: currentRange.from - shift,
          to: currentRange.to - shift
        });
        
        animateButton('scroll-left-btn');
      }
    }

    function scrollRight() {
      if (!chart) return;
      
      const timeScale = chart.timeScale();
      const currentRange = timeScale.getVisibleLogicalRange();
      if (currentRange) {
        const shift = (currentRange.to - currentRange.from) * 0.2; // Scroll by 20%
        timeScale.setVisibleLogicalRange({
          from: currentRange.from + shift,
          to: currentRange.to + shift
        });
        
        animateButton('scroll-right-btn');
      }
    }

    function scrollToEnd() {
      if (!chart || !currentData) return;
      
      chart.timeScale().scrollToPosition(-3, false);
      animateButton('scroll-end-btn');
      console.log('Scrolled to end');
    }

    function scrollToStart() {
      if (!chart || !currentData) return;
      
      chart.timeScale().scrollToPosition(0, false);
      animateButton('scroll-start-btn');
      console.log('Scrolled to start');
    }

    function showBars(count) {
      if (!chart || !currentData) return;
      
      const timeScale = chart.timeScale();
      
      // Update active button
      document.querySelectorAll('.timeframe-controls button').forEach(btn => {
        btn.classList.remove('active');
      });
      
      // Find and activate the clicked button
      const clickedBtn = document.querySelector(`[data-bars="${count}"]`);
      if (clickedBtn) {
        clickedBtn.classList.add('active');
      }
      
      if (count === 0) {
        // Show all bars
        fitContent();
      } else {
        // Show specific number of bars from the end
        const totalBars = currentData.length;
        const from = Math.max(0, totalBars - count);
        
        timeScale.setVisibleLogicalRange({
          from: from,
          to: totalBars
        });
      }
      
      console.log(`Showing ${count === 0 ? 'all' : count} bars`);
    }

    function toggleCrosshair() {
      crosshairEnabled = !crosshairEnabled;
      const btn = document.getElementById('crosshair-btn');
      
      if (crosshairEnabled) {
        chart.applyOptions({
          crosshair: {
            mode: LightweightCharts.CrosshairMode.Normal
          }
        });
        btn.classList.add('active');
        btn.textContent = '✚ Crosshair';
      } else {
        chart.applyOptions({
          crosshair: {
            mode: LightweightCharts.CrosshairMode.Hidden
          }
        });
        btn.classList.remove('active');
        btn.textContent = '✕ Crosshair';
        document.getElementById('chart-info').classList.remove('visible');
      }
      
      animateButton('crosshair-btn');
      console.log(`Crosshair ${crosshairEnabled ? 'enabled' : 'disabled'}`);
    }

    function animateButton(buttonId) {
      const btn = document.getElementById(buttonId);
      if (btn) {
        btn.style.transform = 'scale(0.95)';
        btn.style.background = '#4fc3f7';
        setTimeout(() => {
          btn.style.transform = '';
          btn.style.background = '';
        }, 150);
      }
    }

    // Keyboard Shortcuts
    document.addEventListener('keydown', (e) => {
      // Only trigger shortcuts when not typing in input fields
      if (e.target.tagName !== 'INPUT' && e.target.tagName !== 'TEXTAREA') {
        switch(e.key.toLowerCase()) {
          case 'i':
          case '+':
          case '=':
            e.preventDefault();
            zoomIn();
            break;
          case 'o':
          case '-':
          case '_':
            e.preventDefault();
            zoomOut();
            break;
          case 'r':
            if (!e.ctrlKey && !e.metaKey) {
              e.preventDefault();
              if (e.shiftKey) {
                resetZoom();
              } else {
                refreshData();
              }
            }
            break;
          case 'f':
            if (!e.ctrlKey && !e.metaKey) {
              e.preventDefault();
              fitContent();
            }
            break;
          case 'arrowleft':
            e.preventDefault();
            scrollLeft();
            break;
          case 'arrowright':
            e.preventDefault();
            scrollRight();
            break;
          case 'home':
            e.preventDefault();
            scrollToStart();
            break;
          case 'end':
            e.preventDefault();
            scrollToEnd();
            break;
          case 'c':
            if (!e.ctrlKey && !e.metaKey) {
              e.preventDefault();
              toggleCrosshair();
            }
            break;
          case '1':
            showBars(50);
            break;
          case '2':
            showBars(100);
            break;
          case '3':
            showBars(200);
            break;
          case '4':
            showBars(500);
            break;
          case '5':
            showBars(1000);
            break;
          case '0':
            showBars(0);
            break;
          case 'escape':
            document.getElementById('chart-info').classList.remove('visible');
            break;
        }
      }
    });

    async function loadFile() {
      const filename = document.getElementById('filename-input').value.trim();
      if (!filename) {
        showError('Please enter a filename');
        return;
      }

      const startTime = Date.now();
      try {
        showLoading(true);
        updateStatus('loading', `Loading ${filename}...`);
        
        const response = await fetch(`${API_BASE}/load-file`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ filename: filename })
        });
        
        if (!response.ok) {
          const errorData = await response.json();
          throw new Error(errorData.error || `HTTP ${response.status}`);
        }
        
        const result = await response.json();
        const processingTime = Date.now() - startTime;
        
        if (!result.renko || !Array.isArray(result.renko)) {
          throw new Error('Invalid data format received');
        }

        // Process and display data
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

        if (validData.length === 0) throw new Error('No valid data points found');
        
        validData.sort((a, b) => a.time - b.time);
        renkoSeries.setData(validData);
        currentData = validData;
        currentFile = filename;
        
        setTimeout(() => {
          chart.timeScale().fitContent();
          updateVisibleBarsCount();
        }, 100);
        
        // Update UI
        updateFileStatistics(validData, result);
        document.getElementById('current-file').textContent = filename;
        document.getElementById('api-status').textContent = 'Connected';
        document.getElementById('connection-indicator').className = 'connection-indicator connected';
        document.getElementById('processing-time').textContent = `${processingTime}ms`;
        document.getElementById('last-update').textContent = new Date().toLocaleTimeString();
        
        updateStatus('success', `Loaded ${validData.length} Renko bars from ${filename}`);
        showSuccess(`Successfully loaded ${filename} with ${validData.length} Renko bars`);
        hideError();
        
        // Update server stats
        if (result.stats) {
          document.getElementById('files-processed').textContent = result.stats.files_processed;
          document.getElementById('request-count').textContent = result.stats.requests_served;
        }
        
      } catch (error) {
        console.error('Load failed:', error);
        showError(`Failed to load ${filename}: ${error.message}`);
        updateStatus('error', 'Load failed');
        document.getElementById('api-status').textContent = 'Error';
      } finally {
        showLoading(false);
      }
    }

    async function refreshFileList() {
      try {
        const response = await fetch(`${API_BASE}/list-files`);
        const result = await response.json();
        
        const fileListEl = document.getElementById('file-list');
        if (result.files && result.files.length > 0) {
          fileListEl.innerHTML = result.files.map(file => 
            `<div class="file-item" onclick="selectFile('${file}')">${file}</div>`
          ).join('');
        } else {
          fileListEl.innerHTML = '<div style="color: #ffa726;">No files found in data/tick/</div>';
        }
      } catch (error) {
        console.error('Failed to refresh file list:', error);
        document.getElementById('file-list').innerHTML = '<div style="color: #f44336;">Error loading file list</div>';
      }
    }

    function selectFile(filename) {
      // Remove extension if present
      const cleanName = filename.replace(/\\.(parquet|csv|h5)$/, '');
      document.getElementById('filename-input').value = cleanName;
    }

    function handleEnterKey(event) {
      if (event.key === 'Enter') {
        loadFile();
      }
    }

    function loadSampleData() {
      try {
        showLoading(true);
        updateStatus('loading', 'Generating sample data...');
        
        const sampleData = [];
        const baseTime = Math.floor(Date.now() / 1000) - (100 * 3600);
        let price = 4500;
        
        for (let i = 0; i < 100; i++) {
          const direction = Math.random() > 0.48 ? 1 : -1;
          const brickSize = 25 + (Math.random() * 15);
          const open = price;
          const close = open + (brickSize * direction);
          
          sampleData.push({
            time: baseTime + (i * 3600),
            open: Math.round(open * 100) / 100,
            high: Math.round((Math.max(open, close) + Math.random() * 10) * 100) / 100,
            low: Math.round((Math.min(open, close) - Math.random() * 10) * 100) / 100,
            close: Math.round(close * 100) / 100
          });
          
          price = close;
        }
        
        renkoSeries.setData(sampleData);
        currentData = sampleData;
        currentFile = 'SAMPLE_DATA';
        
        setTimeout(() => {
          chart.timeScale().fitContent();
          updateVisibleBarsCount();
        }, 100);
        
        updateFileStatistics(sampleData, { source: 'Sample Generator' });
        document.getElementById('current-file').textContent = 'Sample Data';
        document.getElementById('api-status').textContent = 'Sample Mode';
        document.getElementById('connection-indicator').className = 'connection-indicator connected';
        
        updateStatus('success', `Generated ${sampleData.length} sample Renko bars`);
        showSuccess(`Generated sample data with ${sampleData.length} Renko bars`);
        hideError();
        
      } catch (e) {
        console.error('Sample data failed:', e);
        updateStatus('error', 'Sample generation failed');
        showError('Failed to generate sample data');
      } finally {
        showLoading(false);
      }
    }

    function updateFileStatistics(data, result) {
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
      
      // Update statistics
      document.getElementById('total-bars').textContent = data.length;
      document.getElementById('data-points').textContent = result.original_rows || 'N/A';
      document.getElementById('price-range').textContent = `$${minPrice.toFixed(2)} - $${maxPrice.toFixed(2)}`;
      document.getElementById('last-close').textContent = `$${lastBar.close.toFixed(2)}`;
      document.getElementById('trend').textContent = upBars > downBars ? 'Bullish ↗' : 'Bearish ↘';
      document.getElementById('brick-count').textContent = data.length;
      
      // Calculate timespan
      const timeSpan = Math.round((lastBar.time - firstBar.time) / 3600);
      document.getElementById('timespan').textContent = `${timeSpan}h`;
    }

    function refreshData() {
      if (currentFile && currentFile !== 'SAMPLE_DATA') {
        loadFile();
      } else if (currentFile === 'SAMPLE_DATA') {
        loadSampleData();
      } else {
        showError('No file selected to refresh');
      }
    }

    function downloadData() {
      if (currentData) {
        const dataStr = JSON.stringify({
          filename: currentFile,
          renko_data: currentData,
          generated_at: new Date().toISOString(),
          total_bars: currentData.length
        }, null, 2);
        const dataBlob = new Blob([dataStr], {type: 'application/json'});
        const url = URL.createObjectURL(dataBlob);
        const link = document.createElement('a');
        link.href = url;
        link.download = `renko-${currentFile}-${new Date().toISOString().slice(0,10)}.json`;
        link.click();
        URL.revokeObjectURL(url);
      } else {
        showError('No data to download');
      }
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
      setTimeout(() => hideError(), 10000); // Auto-hide after 10 seconds
    }

    function hideError() {
      document.getElementById('error-message').style.display = 'none';
    }

    function showSuccess(message) {
      const successElement = document.getElementById('success-message');
      successElement.textContent = message;
      successElement.style.display = 'block';
      setTimeout(() => {
        successElement.style.display = 'none';
      }, 5000);
    }

    // Initialize
    document.addEventListener('DOMContentLoaded', () => {
      if (initChart()) {
        refreshFileList();
        
        // Show keyboard shortcuts help
        console.log('🎮 KEYBOARD SHORTCUTS:');
        console.log('I/+ = Zoom In | O/- = Zoom Out | R = Reset Zoom | F = Fit Content');
        console.log('← → = Scroll | Home/End = Go to Start/End | C = Toggle Crosshair');
        console.log('1-5 = Show specific bars | 0 = Show all | ESC = Hide info');
        console.log('Ctrl+Mouse Wheel = Zoom | Mouse Drag = Pan');
      }
    });
  </script>
</body>
</html>
'''

def get_server_ip():
    """Get server IP address"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return "localhost"

def scan_available_files():
    """Scan for available tick data files"""
    try:
        input_folder = DATA_CONFIG['input_folder']
        if not os.path.exists(input_folder):
            logger.warning(f"Input folder does not exist: {input_folder}")
            return []
        
        files = []
        for ext in DATA_CONFIG['supported_formats']:
            pattern = os.path.join(input_folder, f"*{ext}")
            found_files = glob.glob(pattern)
            files.extend([os.path.basename(f) for f in found_files])
        
        files.sort()
        server_stats['available_files'] = files
        logger.info(f"Found {len(files)} data files: {files}")
        return files
        
    except Exception as e:
        logger.error(f"Error scanning files: {e}")
        return []

def process_tick_data(filename):
    """Process tick data file and generate Renko chart"""
    try:
        server_stats['files_processed'] += 1
        logger.info(f"Processing file: {filename}")
        
        # Determine file path and format
        input_folder = DATA_CONFIG['input_folder']
        file_found = None
        original_rows = 0
        
        # Try different file extensions
        for ext in DATA_CONFIG['supported_formats']:
            potential_path = os.path.join(input_folder, f"{filename}{ext}")
            if os.path.exists(potential_path):
                file_found = potential_path
                break
        
        if not file_found:
            raise FileNotFoundError(f"File {filename} not found in {input_folder}")
        
        logger.info(f"Loading tick data from: {file_found}")
        
        # Load data based on file extension
        if file_found.endswith('.parquet'):
            tick_df = pd.read_parquet(file_found, engine='pyarrow')
        elif file_found.endswith('.csv'):
            tick_df = pd.read_csv(file_found)
        elif file_found.endswith('.h5'):
            tick_df = pd.read_hdf(file_found)
        else:
            raise ValueError(f"Unsupported file format: {file_found}")
        
        original_rows = len(tick_df)
        logger.info(f"Loaded {original_rows} rows from {file_found}")
        
        # Ensure required columns exist
        required_columns = ['price', 'timestamp']
        if 'timestamp' not in tick_df.columns and tick_df.index.name in ['timestamp', 'date', 'time']:
            tick_df = tick_df.reset_index()
        
        missing_cols = [col for col in required_columns if col not in tick_df.columns]
        if missing_cols:
            # Try alternative column names
            column_mapping = {
                'price': ['close', 'last', 'trade_price', 'px_last'],
                'timestamp': ['date', 'time', 'datetime', 'ts']
            }
            
            for missing_col in missing_cols:
                for alt_col in column_mapping.get(missing_col, []):
                    if alt_col in tick_df.columns:
                        tick_df[missing_col] = tick_df[alt_col]
                        logger.info(f"Mapped {alt_col} to {missing_col}")
                        break
        
        # Final check for required columns
        if 'price' not in tick_df.columns:
            raise ValueError("Price column not found. Expected columns: price, close, last, or trade_price")
        
        # Ensure timestamp is datetime
        if 'timestamp' in tick_df.columns:
            tick_df['timestamp'] = pd.to_datetime(tick_df['timestamp'])
            tick_df.set_index('timestamp', inplace=True)
        else:
            # Create artificial timestamps if none exist
            logger.warning("No timestamp column found, creating artificial timestamps")
            tick_df.index = pd.date_range(start='2025-01-01', periods=len(tick_df), freq='1S')
        
        # Add size column if missing
        if 'size' not in tick_df.columns:
            tick_df['size'] = 1
        
        # Resample to OHLC data (1-minute bars)
        logger.info("Converting tick data to OHLC...")
        ohcl_df = tick_df.resample('1min', closed='right', label='right').agg({
            'price': 'ohlc',
            'size': 'sum'
        }).dropna()
        
        ohcl_df.columns = ['open', 'high', 'low', 'close', 'volume']
        
        if len(ohcl_df) == 0:
            raise ValueError("No data remained after resampling to OHLC")
        
        logger.info(f"Created {len(ohcl_df)} OHLC bars from {original_rows} tick records")
        
        # Save OHLC data
        output_folder = DATA_CONFIG['output_folder']
        os.makedirs(output_folder, exist_ok=True)
        output_path = os.path.join(output_folder, f"{filename}_ohlc.csv")
        ohcl_df.to_csv(output_path)
        logger.info(f"Saved OHLC data to: {output_path}")
        
        # Generate Renko chart
        logger.info("Generating Renko chart...")
        retvals = {}
        
        try:
            # Import matplotlib and set backend
            import matplotlib
            matplotlib.use('Agg')
            import matplotlib.pyplot as plt
            plt.ioff()
            
            # Generate Renko chart with mplfinance
            fig = mpf.plot(
                ohcl_df, 
                type='renko', 
                renko_params=dict(
                    brick_size=DATA_CONFIG['renko_params']['brick_size'], 
                    atr_length=DATA_CONFIG['renko_params']['atr_length']
                ), 
                style='yahoo', 
                figsize=(18, 8), 
                returnfig=True,
                title=f"RENKO CHART - {filename}",
                return_calculated_values=retvals,
                savefig=dict(fname=os.path.join(output_folder, f"{filename}_renko.png"), dpi=150)
            )
            
            # Close figure to prevent memory leaks
            if fig and len(fig) > 0:
                plt.close(fig[0])
            
            logger.info(f"Renko calculation completed. Keys: {list(retvals.keys())}")
            
        except Exception as e:
            logger.error(f"Error generating Renko chart with mplfinance: {e}")
            # Fallback: create Renko-like data from OHLC
            logger.info("Creating fallback Renko data...")
            
            # Simple Renko brick calculation
            brick_size = ohcl_df['close'].std() * 0.5  # Use 0.5 std dev as brick size
            renko_bricks = []
            renko_dates = []
            
            last_brick_price = ohcl_df['close'].iloc[0]
            
            for idx, row in ohcl_df.iterrows():
                price_change = row['close'] - last_brick_price
                
                if abs(price_change) >= brick_size:
                    # Create new brick
                    renko_bricks.append(row['close'])
                    renko_dates.append(idx)
                    last_brick_price = row['close']
            
            retvals = {
                'renko_bricks': renko_bricks,
                'renko_dates': renko_dates,
                'renko_size': [brick_size] * len(renko_bricks)
            }
            
            logger.info(f"Created {len(renko_bricks)} fallback Renko bricks")
        
        # Convert retvals to DataFrame
        renko_df = pd.DataFrame(retvals)
        
        if len(renko_df) == 0:
            raise ValueError("No Renko data generated")
        
        # Calculate OHLC for Renko bricks
        renko_df = renko_df.copy()
        renko_df['open'] = renko_df['renko_bricks'].shift(1)
        
        # Set first open price
        if len(renko_df) > 0:
            renko_df.loc[renko_df.index[0], 'open'] = (
                renko_df.loc[renko_df.index[0], 'renko_bricks'] - 
                renko_df.loc[renko_df.index[0], 'renko_size']
            )
        
        # Calculate high, low, close
        renko_df['high'] = renko_df[['open', 'renko_bricks']].max(axis=1) + (renko_df['renko_size'] * 0.1)
        renko_df['low'] = renko_df[['open', 'renko_bricks']].min(axis=1) - (renko_df['renko_size'] * 0.1)
        renko_df['close'] = renko_df['renko_bricks']
        
        logger.info(f"Final Renko DataFrame: {len(renko_df)} bars")
        
        # Cache the result
        cache_key = filename
        renko_cache[cache_key] = {
            'data': renko_df,
            'timestamp': datetime.now(),
            'original_rows': original_rows,
            'file_path': file_found
        }
        
        return renko_df, original_rows
        
    except Exception as e:
        logger.error(f"Error processing {filename}: {e}")
        logger.error(traceback.format_exc())
        server_stats['errors'] += 1
        raise

@app.route('/')
def index():
    """Serve the main interface"""
    try:
        server_ip = get_server_ip()
        uptime = str(datetime.now() - server_stats['start_time']).split('.')[0]
        
        # Scan for available files
        available_files = scan_available_files()
        
        return render_template_string(HTML_TEMPLATE, 
            server_ip=server_ip,
            uptime=uptime,
            requests=server_stats['requests_served'],
            files_processed=server_stats['files_processed'],
            data_folder=DATA_CONFIG['input_folder']
        )
    except Exception as e:
        logger.error(f"Error serving index: {e}")
        return f"Server Error: {e}", 500

@app.route('/api/load-file', methods=['POST'])
def load_file():
    """Load and process a specific tick data file"""
    try:
        start_time = datetime.now()
        server_stats['requests_served'] += 1
        
        data = request.get_json()
        if not data or 'filename' not in data:
            return jsonify({'error': 'Filename is required'}), 400
        
        filename = data['filename'].strip()
        if not filename:
            return jsonify({'error': 'Filename cannot be empty'}), 400
        
        logger.info(f"Processing file request: {filename}")
        
        # Check cache first
        cache_key = filename
        if cache_key in renko_cache:
            cached_data = renko_cache[cache_key]
            cache_age = (datetime.now() - cached_data['timestamp']).total_seconds()
            
            # Use cache if less than 5 minutes old
            if cache_age < 300:
                logger.info(f"Using cached data for {filename} (age: {cache_age:.1f}s)")
                renko_df = cached_data['data']
                original_rows = cached_data['original_rows']
            else:
                logger.info(f"Cache expired for {filename}, reprocessing...")
                renko_df, original_rows = process_tick_data(filename)
        else:
            renko_df, original_rows = process_tick_data(filename)
        
        # Convert DataFrame to JSON format
        renko_data = []
        for idx_pos, (idx, row) in enumerate(renko_df.iterrows()):
            # Handle timestamp
            if 'renko_dates' in renko_df.columns:
                timestamp = row['renko_dates']
            else:
                timestamp = datetime.now() - pd.Timedelta(hours=len(renko_df)-idx_pos)
            
            try:
                if hasattr(timestamp, 'isoformat'):
                    date_iso = timestamp.isoformat()
                else:
                    date_iso = pd.to_datetime(timestamp).isoformat()
            except:
                date_iso = (datetime.now() - pd.Timedelta(hours=len(renko_df)-idx_pos)).isoformat()
            
            renko_data.append({
                'date': date_iso,
                'open': float(row['open']),
                'high': float(row['high']),
                'low': float(row['low']),
                'close': float(row['close'])
            })
        
        processing_time = (datetime.now() - start_time).total_seconds()
        
        response = {
            'renko': renko_data,
            'filename': filename,
            'original_rows': original_rows,
            'renko_bars': len(renko_data),
            'processing_time': round(processing_time, 3),
            'source': 'Real Tick Data',
            'stats': {
                'requests_served': server_stats['requests_served'],
                'files_processed': server_stats['files_processed'],
                'server_uptime': str(datetime.now() - server_stats['start_time']).split('.')[0]
            }
        }
        
        logger.info(f"Successfully processed {filename}: {len(renko_data)} bars in {processing_time:.3f}s")
        return jsonify(response)
        
    except FileNotFoundError as e:
        logger.error(f"File not found: {e}")
        return jsonify({
            'error': f'File not found: {filename}',
            'suggestion': 'Check filename and ensure file exists in data/tick/ folder',
            'available_files': server_stats['available_files']
        }), 404
        
    except Exception as e:
        logger.error(f"Error processing file {filename}: {e}")
        logger.error(traceback.format_exc())
        server_stats['errors'] += 1
        return jsonify({
            'error': str(e),
            'filename': filename,
            'details': 'Check server logs for more information'
        }), 500

@app.route('/api/list-files', methods=['GET'])
def list_files():
    """List available tick data files"""
    try:
        files = scan_available_files()
        return jsonify({
            'files': files,
            'count': len(files),
            'folder': DATA_CONFIG['input_folder'],
            'supported_formats': DATA_CONFIG['supported_formats']
        })
    except Exception as e:
        logger.error(f"Error listing files: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/health', methods=['GET'])
def health_check():
    """Comprehensive health check"""
    try:
        # Check data folder
        data_folder_exists = os.path.exists(DATA_CONFIG['input_folder'])
        available_files = scan_available_files() if data_folder_exists else []
        
        health_status = {
            'status': 'healthy',
            'timestamp': datetime.now().isoformat(),
            'server': {
                'platform': 'Ubuntu Dynamic Server',
                'ip': get_server_ip(),
                'port': 5000,
                'uptime': str(datetime.now() - server_stats['start_time']).split('.')[0]
            },
            'data': {
                'folder_exists': data_folder_exists,
                'folder_path': DATA_CONFIG['input_folder'],
                'available_files': len(available_files),
                'cached_files': len(renko_cache),
                'supported_formats': DATA_CONFIG['supported_formats']
            },
            'stats': server_stats.copy(),
            'config': DATA_CONFIG
        }
        
        # Determine overall health
        if not data_folder_exists:
            health_status['status'] = 'warning'
            health_status['warnings'] = ['Data folder does not exist']
        elif len(available_files) == 0:
            health_status['status'] = 'warning'
            health_status['warnings'] = ['No data files found']
        
        return jsonify(health_status)
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return jsonify({
            'status': 'unhealthy',
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500

@app.route('/api/cache-info', methods=['GET'])
def cache_info():
    """Get information about cached files"""
    try:
        cache_details = {}
        for filename, cache_data in renko_cache.items():
            cache_details[filename] = {
                'cached_at': cache_data['timestamp'].isoformat(),
                'age_seconds': (datetime.now() - cache_data['timestamp']).total_seconds(),
                'bars_count': len(cache_data['data']),
                'original_rows': cache_data['original_rows'],
                'file_path': cache_data['file_path']
            }
        
        return jsonify({
            'cached_files': cache_details,
            'total_cached': len(renko_cache),
            'cache_folder': DATA_CONFIG['output_folder']
        })
    except Exception as e:
        logger.error(f"Error getting cache info: {e}")
        return jsonify({'error': str(e)}), 500

def signal_handler(signum, frame):
    """Graceful shutdown handler"""
    logger.info(f"Received signal {signum}, shutting down gracefully...")
    logger.info(f"Final stats: {server_stats}")
    logger.info(f"Cached files: {list(renko_cache.keys())}")
    sys.exit(0)

if __name__ == '__main__':
    # Set up signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    logger.info("🚀 Starting Dynamic Renko Chart Server...")
    logger.info("=" * 60)
    
    # Check data folder
    if not os.path.exists(DATA_CONFIG['input_folder']):
        logger.warning(f"Data folder does not exist: {DATA_CONFIG['input_folder']}")
        logger.info("Creating data folder...")
        os.makedirs(DATA_CONFIG['input_folder'], exist_ok=True)
    
    # Scan for available files
    available_files = scan_available_files()
    logger.info(f"Found {len(available_files)} data files")
    
    # Get server info
    server_ip = get_server_ip()
    
    print("\n" + "🚀 DYNAMIC RENKO CHART SERVER READY!" + "\n" + "=" * 60)
    print(f"📊 Main Interface: http://{server_ip}:5000")
    print(f"🔌 API Endpoints:")
    print(f"   Load File:     POST http://{server_ip}:5000/api/load-file")
    print(f"   List Files:    GET  http://{server_ip}:5000/api/list-files")
    print(f"   Health Check:  GET  http://{server_ip}:5000/api/health")
    print(f"   Cache Info:    GET  http://{server_ip}:5000/api/cache-info")
    print("=" * 60)
    print(f"📁 Data Folder:   {DATA_CONFIG['input_folder']}")
    print(f"📊 Output Folder: {DATA_CONFIG['output_folder']}")
    print(f"📦 Available Files: {len(available_files)}")
    print(f"🔧 Formats: {', '.join(DATA_CONFIG['supported_formats'])}")
    print("=" * 60)
    print(f"🌐 Network Access: http://{server_ip}:5000 (from any device)")
    print(f"🏠 Local Access:   http://localhost:5000")
    print("=" * 60 + "\n")
    
    # Start the server
    try:
        app.run(
            host='0.0.0.0',    # Accept connections from any IP
            port=5000,         # Use port 5000
            debug=False,       # Disable debug in production
            threaded=True,     # Handle multiple requests
            use_reloader=False # Prevent double startup
        )
    except Exception as e:
        logger.error(f"Failed to start server: {e}")
        print(f"\n❌ SERVER FAILED TO START: {e}")
        print("🔧 Troubleshooting:")
        print("   1. Check if port 5000 is available: sudo netstat -tlnp | grep :5000")
        print("   2. Check firewall: sudo ufw allow 5000")
        print("   3. Check permissions on data folder")
        sys.exit(1)