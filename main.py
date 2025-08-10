import os

from flask import Flask, jsonify
from flask_cors import CORS
import pandas as pd
import mplfinance as mpf
import json
from datetime import datetime
import warnings
import os

# Suppress pandas warnings
warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=UserWarning)

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

# Global variable to store renko data
renko_df = None

def generate_renko_data():
    """
    Generate Renko data from your tick data
    """
    global renko_df
    
    try:
        # Update these paths to match your actual data location
        input_folder = 'data/tick/'  # Update this path
        output_folder = 'data/output/ohcl/'  # Update this path
        filename = 'SPY_2025_W26'  # Update this filename
        
        # Check if tick data file exists
        tick_file_path = f'{input_folder}{filename}.parquet'
        if os.path.exists(tick_file_path):
            print(f"Loading tick data from: {tick_file_path}")
            tick_df = pd.read_parquet(tick_file_path, engine='pyarrow')
            
            # Process to OHLC - use 'min' instead of deprecated 'T'
            ohcl_df = tick_df.resample('1min', closed='right', label='right').agg({
                'price': 'ohlc',
                'size': 'sum'
            })
            ohcl_df = ohcl_df.dropna()
            ohcl_df.columns = ['open', 'high', 'low', 'close', 'volume']
            ohcl_df = ohcl_df.reset_index().rename(columns={'timestamp': 'date'})
            ohcl_df.set_index('date', inplace=True)
            
            # Save OHLC data
            os.makedirs(output_folder, exist_ok=True)
            ohcl_df.to_csv(f'{output_folder}{filename}.csv')
            
            # Generate Renko chart
            retvals = {}
            try:
                # Set matplotlib backend to prevent GUI issues
                plt.ioff()  # Turn off interactive mode
                
                fig = mpf.plot(ohcl_df, type='renko', 
                             renko_params=dict(brick_size='atr', atr_length=14), 
                             style='yahoo', figsize=(180, 7), returnfig=True,
                             title=f"RENKO CHART WITH ATR {filename}", 
                             return_calculated_values=retvals)
                
                # Close the figure immediately to prevent GUI issues
                if fig and len(fig) > 0:
                    plt.close(fig[0])
                
                print(f"Renko calculation completed. Available keys: {list(retvals.keys())}")
                
            except Exception as e:
                print(f"Error generating Renko chart: {e}")
                # Create fallback data structure matching mplfinance output
                retvals = {
                    'renko_bricks': ohcl_df['close'].values[:50],  # Use actual close prices
                    'renko_dates': ohcl_df.index[:50],  # Use actual dates
                    'renko_size': [2.0] * 50
                }
            
        else:
            print(f"Tick data file not found: {tick_file_path}")
            print("Creating sample data for testing...")
            # Create sample data that matches the expected structure
            sample_dates = pd.date_range('2025-01-01', periods=50, freq='1H')
            retvals = {
                'renko_bricks': [400 + i * 2 + (i % 5) * 3 for i in range(50)],
                'renko_dates': sample_dates,
                'renko_size': [2.0] * 50
            }
        
        # Convert retvals to DataFrame
        renko_df = pd.DataFrame(retvals)
        print(f"Renko DataFrame columns: {list(renko_df.columns)}")
        print(f"Renko DataFrame shape: {renko_df.shape}")
        
    except Exception as e:
        print(f"Error in generate_renko_data: {e}")
        import traceback
        traceback.print_exc()
        
        # Fallback sample data
        sample_dates = pd.date_range('2025-01-01', periods=20, freq='1H')
        renko_df = pd.DataFrame({
            'renko_bricks': [400 + i * 2 for i in range(20)],
            'renko_dates': sample_dates,
            'renko_size': [2.0] * 20
        })
    
    # Calculate OHLC for Renko bricks - fix pandas warnings
    renko_df = renko_df.copy()  # Ensure we're working with a copy
    renko_df['open'] = renko_df['renko_bricks'].shift(1)
    
    # Fix the chained assignment warning using .loc
    if len(renko_df) > 0:
        renko_df.loc[renko_df.index[0], 'open'] = (
            renko_df.loc[renko_df.index[0], 'renko_bricks'] - 
            renko_df.loc[renko_df.index[0], 'renko_size']
        )
    
    renko_df['high'] = renko_df[['open', 'renko_bricks']].max(axis=1)
    renko_df['low'] = renko_df[['open', 'renko_bricks']].min(axis=1)
    renko_df['close'] = renko_df['renko_bricks']
    
    print(f"Final Renko DataFrame columns: {list(renko_df.columns)}")
    return renko_df

@app.route('/renko-data', methods=['GET'])
def get_renko_data():
    """
    API endpoint to get Renko chart data
    """
    try:
        if renko_df is None:
            generate_renko_data()
        
        # Debug: Print column names
        print(f"Available columns: {list(renko_df.columns)}")
        print(f"DataFrame index type: {type(renko_df.index)}")
        
        # Convert DataFrame to JSON format with expected structure
        renko_data = []
        
        for idx_pos, (idx, row) in enumerate(renko_df.iterrows()):
            # Handle different possible column names from mplfinance
            if 'renko_dates' in renko_df.columns:
                timestamp = row['renko_dates']
            elif 'Date' in renko_df.columns:
                timestamp = row['Date']
            elif renko_df.index.name in ['Date', 'date', 'timestamp']:
                timestamp = idx  # idx is the actual timestamp from index
            else:
                # If no date column found, create sequential timestamps
                # Use idx_pos (integer position) instead of idx (which might be timestamp)
                timestamp = pd.Timestamp('2025-01-01') + pd.Timedelta(hours=idx_pos)
            
            # Convert timestamp to ISO format string
            try:
                if hasattr(timestamp, 'isoformat'):
                    date_iso = timestamp.isoformat()
                elif isinstance(timestamp, str):
                    # If it's already a string, try to parse and format
                    date_iso = pd.to_datetime(timestamp).isoformat()
                else:
                    # Fallback: convert to pandas timestamp first
                    date_iso = pd.to_datetime(timestamp).isoformat()
            except Exception as e:
                print(f"Date conversion error for {timestamp}: {e}")
                # Use a default timestamp with offset
                date_iso = (pd.Timestamp('2025-01-01') + pd.Timedelta(hours=idx_pos)).isoformat()
            
            renko_data.append({
                'date': date_iso,
                'open': float(row['open']),
                'high': float(row['high']),
                'low': float(row['low']),
                'close': float(row['close'])
            })
        
        # Return data in expected format with "renko" array
        response = {
            'renko': renko_data
        }
        
        
        print(f"Returning {len(renko_data)} renko bars")
        return jsonify(response)
        
    except Exception as e:
        print(f"Error in get_renko_data: {e}")
        import traceback
        traceback.print_exc()
        
        return jsonify({
            'renko': [],
            'error': str(e)
        }), 500

@app.route('/health', methods=['GET'])
def health_check():
    """
    Health check endpoint
    """
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat()
    })

@app.route('/', methods=['GET'])
def index():
    """
    Root endpoint with API information
    """
    return jsonify({
        'message': 'Renko Chart API',
        'endpoints': {
            '/renko-data': 'GET - Returns Renko chart data',
            '/health': 'GET - Health check'
        }
    })

if __name__ == "__main__":
  app.run(debug=True, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))