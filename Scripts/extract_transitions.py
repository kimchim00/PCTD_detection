"""
VCD File Analyzer - Extract Transition Frequencies from Simulation
Fixed version with better error handling
"""

import re
import json
from collections import defaultdict
from pathlib import Path

class VCDAnalyzer:
    def __init__(self, vcd_file):
        self.vcd_file = vcd_file
        self.signals = {}
        self.transitions = defaultdict(int)
        self.signal_values = defaultdict(list)
        self.timescale = "1ns"
        self.simulation_time = 0
        
    def parse_vcd(self):
        """Parse VCD file and extract signal information"""
        print(f"Parsing VCD file: {self.vcd_file}")
        
        try:
            with open(self.vcd_file, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
        except Exception as e:
            print(f"Error reading file: {e}")
            return
        
        in_dump_section = False
        current_time = 0
        line_num = 0
        
        for line in lines:
            line_num += 1
            line = line.strip()
            
            if not line:
                continue
            
            # Parse timescale with better error handling
            if line.startswith('$timescale'):
                try:
                    parts = line.split()
                    if len(parts) >= 2:
                        self.timescale = parts[1]
                    else:
                        # Handle "$timescale 1ns $end" format
                        match = re.search(r'(\d+\s*[a-z]+)', line, re.IGNORECASE)
                        if match:
                            self.timescale = match.group(1)
                    print(f"Timescale: {self.timescale}")
                except Exception as e:
                    print(f"Warning: Could not parse timescale at line {line_num}: {e}")
                    self.timescale = "1ns"
                    
            # Parse variable declarations
            elif line.startswith('$var'):
                try:
                    parts = line.split()
                    if len(parts) >= 5:
                        var_type = parts[1]
                        var_size = parts[2]
                        var_id = parts[3]
                        var_name = parts[4]
                        
                        self.signals[var_id] = {
                            'name': var_name,
                            'type': var_type,
                            'size': var_size,
                            'last_value': None
                        }
                except Exception as e:
                    print(f"Warning: Could not parse variable at line {line_num}: {e}")
                    
            # Parse time stamps
            elif line.startswith('#'):
                try:
                    current_time = int(line[1:])
                    self.simulation_time = max(self.simulation_time, current_time)
                    in_dump_section = True
                except Exception as e:
                    print(f"Warning: Could not parse timestamp at line {line_num}: {e}")
                    
            # Parse value changes
            elif in_dump_section and line and not line.startswith('$'):
                try:
                    # Single bit value change: 0x, 1x, etc
                    if len(line) >= 2 and line[0] in '01xzXZ':
                        value = line[0]
                        signal_id = line[1:]
                        
                        if signal_id in self.signals:
                            signal_name = self.signals[signal_id]['name']
                            last_value = self.signals[signal_id]['last_value']
                            
                            if last_value is not None and last_value != value:
                                if value in '01' and last_value in '01':
                                    self.transitions[signal_name] += 1
                            
                            self.signals[signal_id]['last_value'] = value
                            self.signal_values[signal_name].append((current_time, value))
                            
                    # Bus value change: b0101 x
                    elif line.startswith('b'):
                        parts = line.split()
                        if len(parts) >= 2:
                            value = parts[0][1:]  # Remove 'b' prefix
                            signal_id = parts[1]
                            
                            if signal_id in self.signals:
                                signal_name = self.signals[signal_id]['name']
                                last_value = self.signals[signal_id]['last_value']
                                
                                if last_value is not None and last_value != value:
                                    self.transitions[signal_name] += 1
                                
                                self.signals[signal_id]['last_value'] = value
                                self.signal_values[signal_name].append((current_time, value))
                                
                    # Real number value: r1.234 x
                    elif line.startswith('r'):
                        parts = line.split()
                        if len(parts) >= 2:
                            value = parts[0][1:]
                            signal_id = parts[1]
                            
                            if signal_id in self.signals:
                                signal_name = self.signals[signal_id]['name']
                                last_value = self.signals[signal_id]['last_value']
                                
                                if last_value is not None and last_value != value:
                                    self.transitions[signal_name] += 1
                                
                                self.signals[signal_id]['last_value'] = value
                                
                except Exception as e:
                    # Skip problematic lines silently
                    pass
        
        print(f"Total simulation time: {self.simulation_time} {self.timescale}")
        print(f"Total signals parsed: {len(self.signals)}")
        print(f"Signals with transitions: {len(self.transitions)}")
        
    def calculate_frequencies(self):
        """Calculate transition frequencies"""
        frequencies = {}
        
        # Convert to nanoseconds
        time_multiplier = 1
        timescale_lower = self.timescale.lower()
        
        if 'ns' in timescale_lower:
            time_multiplier = 1
        elif 'us' in timescale_lower:
            time_multiplier = 1000
        elif 'ms' in timescale_lower:
            time_multiplier = 1000000
        elif 'ps' in timescale_lower:
            time_multiplier = 0.001
        
        time_ns = self.simulation_time * time_multiplier
        
        for signal_name, count in self.transitions.items():
            if time_ns > 0:
                freq = count / time_ns
                frequencies[signal_name] = freq
            else:
                frequencies[signal_name] = 0.0
        
        return frequencies
    
    def identify_dff_signals(self, frequencies):
        """Identify DFF output signals"""
        dff_signals = {}
        
        dff_patterns = [
            r'.*_Q$',
            r'.*_q$',
            r'.*_reg\[.*\]$',
            r'.*_reg$',
            r'.*dff.*',
            r'.*state.*',
            r'.*[Cc]ntr.*',
            r'.*[Cc]ount.*',
            r'.*[Ss]hift.*',
            r'.*_ff.*',
            r'q\[.*\]$',
        ]
        
        for signal_name, freq in frequencies.items():
            for pattern in dff_patterns:
                if re.match(pattern, signal_name, re.IGNORECASE):
                    dff_signals[signal_name] = freq
                    break
        
        return dff_signals
    
    def generate_report(self, output_file='transition_report.txt'):
        """Generate detailed report"""
        frequencies = self.calculate_frequencies()
        dff_signals = self.identify_dff_signals(frequencies)
        
        if not frequencies:
            print("Warning: No frequencies calculated")
            return {}, {}
        
        values = list(frequencies.values())
        trans_counts = list(self.transitions.values())
        
        stats = {
            'total_signals': len(frequencies),
            'min_freq': min(values) if values else 0,
            'max_freq': max(values) if values else 0,
            'avg_freq': sum(values) / len(values) if values else 0,
            'zero_transitions': sum(1 for v in values if v == 0),
            'min_trans': min(trans_counts) if trans_counts else 0,
            'max_trans': max(trans_counts) if trans_counts else 0,
            'avg_trans': sum(trans_counts) / len(trans_counts) if trans_counts else 0,
        }
        
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write("="*80 + "\n")
            f.write("TRANSITION FREQUENCY ANALYSIS REPORT\n")
            f.write("="*80 + "\n\n")
            
            f.write(f"VCD File: {self.vcd_file}\n")
            f.write(f"Simulation Time: {self.simulation_time} {self.timescale}\n")
            f.write(f"Total Signals: {stats['total_signals']}\n")
            f.write(f"DFF Signals Identified: {len(dff_signals)}\n\n")
            
            f.write("STATISTICS:\n")
            f.write(f"  Transition Counts:\n")
            f.write(f"    Min: {stats['min_trans']}\n")
            f.write(f"    Max: {stats['max_trans']}\n")
            f.write(f"    Avg: {stats['avg_trans']:.2f}\n\n")
            f.write(f"  Frequencies:\n")
            f.write(f"    Min: {stats['min_freq']:.6e}\n")
            f.write(f"    Max: {stats['max_freq']:.6e}\n")
            f.write(f"    Avg: {stats['avg_freq']:.6e}\n\n")
            f.write(f"  Signals with zero transitions: {stats['zero_transitions']}\n\n")
            
            # All signals sorted by transition count
            f.write("-"*80 + "\n")
            f.write("ALL SIGNALS (Top 50 by transition count)\n")
            f.write("-"*80 + "\n")
            f.write(f"{'Signal Name':<40} {'Transitions':>15} {'Frequency':>15}\n")
            f.write("-"*80 + "\n")
            
            sorted_all = sorted(self.transitions.items(), key=lambda x: x[1], reverse=True)
            for signal_name, count in sorted_all[:50]:
                freq = frequencies.get(signal_name, 0)
                f.write(f"{signal_name:<40} {count:>15} {freq:>15.6e}\n")
            
            f.write("\n" + "-"*80 + "\n")
            f.write("DFF SIGNALS ONLY\n")
            f.write("-"*80 + "\n")
            f.write(f"{'Signal Name':<40} {'Transitions':>15} {'Frequency':>15}\n")
            f.write("-"*80 + "\n")
            
            sorted_dff = sorted(dff_signals.items(), key=lambda x: self.transitions.get(x[0], 0), reverse=True)
            for signal_name, freq in sorted_dff:
                count = self.transitions[signal_name]
                f.write(f"{signal_name:<40} {count:>15} {freq:>15.6e}\n")
            
            # Suspicious low-activity signals
            if dff_signals:
                dff_counts = [self.transitions[s] for s in dff_signals.keys()]
                threshold = sum(dff_counts) / len(dff_counts) * 0.1
                suspicious = [(s, self.transitions[s]) for s in dff_signals.keys() if self.transitions[s] < threshold]
                
                if suspicious:
                    f.write("\n" + "-"*80 + "\n")
                    f.write("WARNING: SUSPICIOUS LOW-ACTIVITY DFF SIGNALS\n")
                    f.write(f"    (Less than 10% of average: {threshold:.2f} transitions)\n")
                    f.write("-"*80 + "\n")
                    f.write(f"{'Signal Name':<40} {'Transitions':>15} {'% of Avg':>15}\n")
                    f.write("-"*80 + "\n")
                    
                    for signal_name, count in sorted(suspicious, key=lambda x: x[1]):
                        pct = (count / stats['avg_trans'] * 100) if stats['avg_trans'] > 0 else 0
                        f.write(f"{signal_name:<40} {count:>15} {pct:>14.2f}%\n")
        
        print(f"\n✅ Report generated: {output_file}")
        print(f"\nSummary:")
        print(f"  Total signals: {stats['total_signals']}")
        print(f"  DFF signals: {len(dff_signals)}")
        print(f"  Avg transitions: {stats['avg_trans']:.2f}")
        
        return frequencies, dff_signals
    
    def save_json(self, all_signals_file='transition_frequencies.json', 
                  dff_signals_file='dff_transition_frequencies.json'):
        """Save to JSON files"""
        frequencies = self.calculate_frequencies()
        dff_signals = self.identify_dff_signals(frequencies)
        
        # Also save transition counts
        all_data = {
            'frequencies': frequencies,
            'transition_counts': dict(self.transitions)
        }
        
        dff_data = {
            'frequencies': dff_signals,
            'transition_counts': {s: self.transitions[s] for s in dff_signals.keys()}
        }
        
        with open(all_signals_file, 'w') as f:
            json.dump(all_data, f, indent=2)
        print(f"✅ All signals saved: {all_signals_file}")
        
        with open(dff_signals_file, 'w') as f:
            json.dump(dff_data, f, indent=2)
        print(f"✅ DFF signals saved: {dff_signals_file}")
        
        return frequencies, dff_signals


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: py extract_transitions.py <vcd_file>")
        sys.exit(1)
    
    vcd_file = sys.argv[1]
    
    if not Path(vcd_file).exists():
        print(f"Error: VCD file not found: {vcd_file}")
        sys.exit(1)
    
    print("\n" + "="*80)
    print("VCD TRANSITION FREQUENCY ANALYZER")
    print("="*80 + "\n")
    
    analyzer = VCDAnalyzer(vcd_file)
    analyzer.parse_vcd()
    analyzer.generate_report()
    analyzer.save_json()
    
    print("\n" + "="*80)
    print("✅ Analysis complete!")
    print("="*80 + "\n")