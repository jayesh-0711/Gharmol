import pandas as pd
import json
import time
import os
from geopy.geocoders import Nominatim
import concurrent.futures

def generate_heatmap_data():
    df = pd.read_csv("data/Bengaluru_House_Data.csv")
    df = df.dropna(subset=['location', 'price', 'total_sqft'])
    
    def convert_sqft(x):
        try:
            if '-' in str(x):
                a, b = x.split('-')
                return (float(a) + float(b)) / 2
            return float(x)
        except:
            return None

    df['total_sqft_cleaned'] = df['total_sqft'].apply(convert_sqft)
    df = df.dropna(subset=['total_sqft_cleaned'])
    df['price_per_sqft'] = df['price'] * 100000 / df['total_sqft_cleaned']
    
    avg_prices = df.groupby('location')['price_per_sqft'].mean()
    location_counts = df['location'].value_counts()
    
    all_locations = location_counts.index.tolist()
    
    cache_file = "geocodes_cache.json"
    cache = {}
    if os.path.exists(cache_file):
        with open(cache_file, "r") as f:
            cache = json.load(f)
            
    print(f"Total unique locations to map: {len(all_locations)}")
    
    # User asked for ALL data
    targets = [loc for loc in all_locations if loc not in cache]
    
    print(f"Geocoding {len(targets)} new locations concurrently...")
    
    def fetch_location(loc):
        # We must create a new Nominatim instance per thread or it sometimes hangs
        geolocator = Nominatim(user_agent=f"bengaluru_heatmap_v2_{os.urandom(4).hex()}")
        try:
            query = f"{loc}, Bengaluru, India"
            location = geolocator.geocode(query, timeout=5)
            # Small delay to reduce 429 errors from Nominatim but threaded gives overall speedup
            time.sleep(0.3)
            if location:
                return loc, {'lat': location.latitude, 'lng': location.longitude}
            else:
                return loc, None
        except Exception:
            time.sleep(1)
            return loc, None

    # Fetch with 4 threads (to speed it up to ~2 minutes without hitting hard API blocks)
    completed = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        future_to_loc = {executor.submit(fetch_location, loc): loc for loc in targets}
        for future in concurrent.futures.as_completed(future_to_loc):
            loc = future_to_loc[future]
            try:
                res_loc, data = future.result()
                cache[res_loc] = data
                completed += 1
                if completed % 100 == 0:
                    print(f"Completed {completed}/{len(targets)}")
            except Exception as e:
                cache[loc] = None

    # Final save of cache
    with open(cache_file, "w") as f:
        json.dump(cache, f)

    heatmap_data = []
    
    # Build complete heatmap data using everything in the cache
    for loc in all_locations:
        if loc in cache and cache[loc] is not None:
            heatmap_data.append([
                cache[loc]['lat'], 
                cache[loc]['lng'], 
                avg_prices[loc], 
                int(location_counts[loc]), 
                str(loc)
            ])
            
    # Normalize intensities 0..1
    if heatmap_data:
        prices = [item[2] for item in heatmap_data]
        min_price = min(prices)
        max_price = max(prices)
        
        sorted_prices = sorted(prices)
        p95 = sorted_prices[int(len(sorted_prices)*0.95)]
        p05 = sorted_prices[int(len(sorted_prices)*0.05)]
        
        if p95 > p05:
            for item in heatmap_data:
                clipped_price = max(p05, min(p95, item[2]))
                item[2] = (clipped_price - p05) / (p95 - p05)
        else:
            for item in heatmap_data:
                item[2] = 0.5
                
    with open("static/heatmap_data.json", "w") as f:
        json.dump(heatmap_data, f)
        
    print(f"Saved {len(heatmap_data)} accurate points representing ALL DATA to static/heatmap_data.json")

if __name__ == "__main__":
    generate_heatmap_data()
