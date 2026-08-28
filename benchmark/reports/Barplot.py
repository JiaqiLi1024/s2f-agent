import matplotlib.pyplot as plt
import numpy as np
import csv
import os

# 1. Prepare data
categories = ['Routing', 'Groundedness', 'Task Success', 'Overall']
csv_suites = ['routing', 'groundedness', 'task_success', 'overall']

# Target models to plot
target_models = ['s2f-agent', 'gpt-4o', 'o3-mini']
data = {model: [0.0] * len(categories) for model in target_models}

csv_file = 'benchmark-summary-full_20260413_233845.csv'

# Read CSV file to build data dynamically
if os.path.exists(csv_file):
    print(f"Reading data from {csv_file}...")
    # Use utf-8-sig to handle possible BOM in CSV
    with open(csv_file, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            model = row['participant_id']
            suite = row['suite']
            if model in target_models and suite in csv_suites:
                idx = csv_suites.index(suite)
                # Extract 'micro' column and convert to percentage (%)
                data[model][idx] = float(row['micro']) * 100
else:
    print(f"'{csv_file}' not found in the current directory.")
    exit(1)

# Academic color palette (colorblind-friendly)
colors = {
    's2f-agent': '#2563EB',  # Theme blue - emphasizes our work
    'gpt-4o': '#F59E0B',     # Amber - baseline model 1
    'o3-mini': '#10B981'     # Emerald - baseline model 2
}

# Uncomment below to include ablation data
# ablation_data = {
#     'o3-mini (direct)': [0.0, 0.0, 0.0, 0.0],
#     'o3-mini (catalog-only)': [16.7, 0.0, 18.2, 15.2]
# }

# 2. Set basic plot parameters
plt.rcParams['font.family'] = 'sans-serif'
plt.rcParams['font.sans-serif'] = ['Arial', 'Helvetica', 'DejaVu Sans'] # Prefer common academic fonts
plt.rcParams['axes.axisbelow'] = True # Put grid lines behind bars

fig, ax = plt.subplots(figsize=(10, 6), dpi=300) # dpi=300 ensures publication-quality resolution

x = np.arange(len(categories))  # Label locations
width = 0.25  # Width of the bars
multiplier = 0 # Multiplier to shift bars for different models

# 3. Plot the bars
for attribute, measurement in data.items():
    offset = width * multiplier
    # Calculate x position for the current model
    rects = ax.bar(x + offset - width, measurement, width, label=attribute, color=colors[attribute], edgecolor='white', linewidth=1)
    
    # Add precise value labels on top of the bars to highlight 100% and 0%
    for rect in rects:
        height = rect.get_height()
        # Special handling for 0.0 to float slightly for better readability
        y_pos = height + 1.5 if height < 5 else height + 1.5
        ax.annotate(f'{height:.1f}%',
                    xy=(rect.get_x() + rect.get_width() / 2, y_pos),
                    xytext=(0, 0),  
                    textcoords="offset points",
                    ha='center', va='bottom',
                    fontsize=9,
                    fontweight='bold',
                    color=colors[attribute])
        
    multiplier += 1

# 4. Beautify plot (academic style optimization)
ax.set_ylabel('Micro Accuracy (%)', fontsize=12, fontweight='bold', labelpad=10)
ax.set_title('Performance Benchmark: s2f-agent vs. Generalist Models', fontsize=14, fontweight='bold', pad=20)
ax.set_xticks(x)
ax.set_xticklabels(categories, fontsize=11, fontweight='bold')
ax.set_ylim(0, 115) # Leave space at the top to prevent label cutoff

# Customize grid: keep horizontal dashed lines to assist reading
ax.yaxis.grid(True, linestyle='--', alpha=0.7, color='#E5E7EB')
ax.xaxis.grid(False)

# Remove top and right spines for a clean, modern look
ax.spines['top'].set_visible(False)
ax.spines['right'].set_visible(False)
ax.spines['left'].set_color('#9CA3AF')
ax.spines['bottom'].set_color('#9CA3AF')
ax.tick_params(axis='both', colors='#4B5563', length=0)

# Set legend
ax.legend(loc='upper right', frameon=False, fontsize=10, ncol=3)

# Auto-adjust layout
fig.tight_layout()

# 5. Save plot in high-res PDF and PNG formats
plt.savefig('benchmark_results.pdf', format='pdf', bbox_inches='tight')
plt.savefig('benchmark_results.png', format='png', bbox_inches='tight', dpi=300)

print("Plot successfully generated and saved as benchmark_results.pdf and benchmark_results.png")

# Display the plot in interactive environments
plt.show()