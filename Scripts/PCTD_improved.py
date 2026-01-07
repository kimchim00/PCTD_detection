#!/usr/bin/env python3
"""
PCTD (Petri net-based Controllability and Detectability Trojan Detection)
Improved version for Hardware Trojan Detection
"""

import json
import re
import sys
from pathlib import Path
from collections import defaultdict

class PCTDDetector:
    def __init__(self, verilog_file, transition_file):
        self.verilog_file = verilog_file
        self.transition_file = transition_file
        
        # Parse data
        self.transition_data = {}
        self.dff_list = []
        self.nets = {}
        self.modules = []
        
        # Detection parameters
        self.threshold_percentile = 10  # Bottom 10% are suspicious
        self.min_transition_ratio = 0.1  # Less than 10% of average
        
        # Results
        self.suspicious_signals = []
        self.trojan_candidates = []
        
    def load_transition_data(self):
        """Load transition frequency data from JSON"""
        print(f"\n[1/5] Loading transition data from: {self.transition_file}")
        
        try:
            with open(self.transition_file, 'r') as f:
                data = json.load(f)
            
            # Handle both old and new format
            if 'transition_counts' in data:
                self.transition_data = data['transition_counts']
            else:
                # Old format - just frequencies
                self.transition_data = data
            
            print(f"  ✓ Loaded data for {len(self.transition_data)} signals")
            
            # Calculate statistics
            if self.transition_data:
                counts = [v for v in self.transition_data.values() if isinstance(v, (int, float))]
                if counts:
                    self.avg_transitions = sum(counts) / len(counts)
                    self.max_transitions = max(counts)
                    self.min_transitions = min(counts)
                    
                    print(f"  ✓ Transition statistics:")
                    print(f"      Min: {self.min_transitions}")
                    print(f"      Max: {self.max_transitions}")
                    print(f"      Avg: {self.avg_transitions:.2f}")
                    
        except FileNotFoundError:
            print(f"  ✗ Error: File not found: {self.transition_file}")
            sys.exit(1)
        except json.JSONDecodeError as e:
            print(f"  ✗ Error: Invalid JSON format: {e}")
            sys.exit(1)
    
    def parse_verilog(self):
        """Parse Verilog file to extract circuit structure"""
        print(f"\n[2/5] Parsing Verilog file: {self.verilog_file}")
        
        try:
            with open(self.verilog_file, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
        except FileNotFoundError:
            print(f"  ✗ Error: Verilog file not found: {self.verilog_file}")
            sys.exit(1)
        
        # Extract module names
        module_pattern = r'module\s+(\w+)'
        self.modules = re.findall(module_pattern, content)
        print(f"  ✓ Found {len(self.modules)} modules: {', '.join(self.modules)}")
        
        # Extract register/wire declarations
        reg_pattern = r'(?:reg|wire)\s+(?:\[.*?\])?\s*(\w+)'
        signals = re.findall(reg_pattern, content)
        print(f"  ✓ Found {len(signals)} signal declarations")
        
        # Extract always blocks (potential DFF locations)
        always_pattern = r'always\s*@\s*\(([^)]+)\)'
        always_blocks = re.findall(always_pattern, content)
        print(f"  ✓ Found {len(always_blocks)} always blocks")
        
        # Extract signals that are assigned in always @ (posedge/negedge) - these are likely DFFs
        dff_pattern = r'always\s*@\s*\((?:posedge|negedge)[^)]*\)[\s\S]*?begin[\s\S]*?end'
        dff_blocks = re.findall(dff_pattern, content)
        
        # Extract signal names from DFF blocks
        for block in dff_blocks:
            # Find assignments in the block
            assign_pattern = r'(\w+)\s*<=|(\w+)\s*='
            assigned_signals = re.findall(assign_pattern, block)
            for sig_tuple in assigned_signals:
                sig = sig_tuple[0] or sig_tuple[1]
                if sig and sig not in self.dff_list:
                    self.dff_list.append(sig)
        
        print(f"  ✓ Identified {len(self.dff_list)} potential DFF signals from code structure")
    
    def identify_suspicious_signals(self):
        """Identify signals with abnormally low transition counts"""
        print(f"\n[3/5] Identifying suspicious low-activity signals...")
        
        if not self.transition_data:
            print("  ✗ No transition data available")
            return
        
        # Calculate threshold
        counts = [v for v in self.transition_data.values() if isinstance(v, (int, float)) and v > 0]
        if not counts:
            print("  ✗ No valid transition counts found")
            return
        
        counts_sorted = sorted(counts)
        threshold_index = max(0, int(len(counts_sorted) * self.threshold_percentile / 100))
        threshold = counts_sorted[threshold_index]
        
        print(f"  ✓ Threshold (bottom {self.threshold_percentile}%): {threshold:.2f} transitions")
        print(f"  ✓ Average transitions: {self.avg_transitions:.2f}")
        
        # Find signals below threshold
        for signal, count in self.transition_data.items():
            if isinstance(count, (int, float)) and count < threshold and count > 0:
                suspicion_score = 1.0 - (count / self.avg_transitions)
                self.suspicious_signals.append({
                    'name': signal,
                    'transitions': count,
                    'suspicion_score': suspicion_score,
                    'percentage_of_avg': (count / self.avg_transitions * 100) if self.avg_transitions > 0 else 0
                })
        
        # Sort by transition count (lowest first)
        self.suspicious_signals.sort(key=lambda x: x['transitions'])
        
        print(f"  ✓ Found {len(self.suspicious_signals)} suspicious signals")
        
        if self.suspicious_signals:
            print(f"\n  Top 5 most suspicious:")
            for i, sig in enumerate(self.suspicious_signals[:5], 1):
                print(f"    {i}. {sig['name']}: {sig['transitions']} transitions ({sig['percentage_of_avg']:.2f}% of avg)")
    
    def analyze_trojan_candidates(self):
        """Analyze suspicious signals to identify trojan candidates"""
        print(f"\n[4/5] Analyzing Trojan candidates...")
        
        # Cross-reference with DFF signals from Verilog
        for sus_sig in self.suspicious_signals:
            signal_name = sus_sig['name']
            
            # Check if signal matches any DFF pattern or is in DFF list
            is_dff = False
            
            # Check against extracted DFF list
            for dff in self.dff_list:
                if dff in signal_name or signal_name in dff:
                    is_dff = True
                    break
            
            # Check against common DFF naming patterns
            dff_patterns = [
                r'.*_reg\[?\d*\]?$',
                r'.*_q\[?\d*\]?$',
                r'.*state.*',
                r'.*count.*',
                r'.*shift.*',
            ]
            
            if not is_dff:
                for pattern in dff_patterns:
                    if re.match(pattern, signal_name, re.IGNORECASE):
                        is_dff = True
                        break
            
            if is_dff:
                # Calculate trojan probability
                trojan_probability = sus_sig['suspicion_score'] * 100
                
                # High suspicion if very low activity
                if sus_sig['percentage_of_avg'] < 5:
                    risk_level = "CRITICAL"
                elif sus_sig['percentage_of_avg'] < 10:
                    risk_level = "HIGH"
                elif sus_sig['percentage_of_avg'] < 20:
                    risk_level = "MEDIUM"
                else:
                    risk_level = "LOW"
                
                self.trojan_candidates.append({
                    'signal': signal_name,
                    'transitions': sus_sig['transitions'],
                    'percentage_of_avg': sus_sig['percentage_of_avg'],
                    'trojan_probability': trojan_probability,
                    'risk_level': risk_level
                })
        
        # Sort by trojan probability
        self.trojan_candidates.sort(key=lambda x: x['trojan_probability'], reverse=True)
        
        print(f"  ✓ Identified {len(self.trojan_candidates)} potential Trojan candidates")
    
    def generate_report(self, output_file='pctd_detection_report.txt'):
        """Generate comprehensive detection report"""
        print(f"\n[5/5] Generating detection report...")
        
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write("="*80 + "\n")
            f.write("PCTD HARDWARE TROJAN DETECTION REPORT\n")
            f.write("="*80 + "\n\n")
            
            f.write(f"Verilog File: {self.verilog_file}\n")
            f.write(f"Transition Data: {self.transition_file}\n")
            f.write(f"Detection Threshold: Bottom {self.threshold_percentile}% of activity\n\n")
            
            f.write("-"*80 + "\n")
            f.write("ANALYSIS SUMMARY\n")
            f.write("-"*80 + "\n")
            f.write(f"Total signals analyzed: {len(self.transition_data)}\n")
            f.write(f"Suspicious signals found: {len(self.suspicious_signals)}\n")
            f.write(f"Trojan candidates (DFF signals): {len(self.trojan_candidates)}\n")
            f.write(f"Average transitions: {self.avg_transitions:.2f}\n\n")
            
            if self.trojan_candidates:
                f.write("-"*80 + "\n")
                f.write("TROJAN CANDIDATES (Ranked by suspicion)\n")
                f.write("-"*80 + "\n")
                f.write(f"{'Signal Name':<30} {'Trans':>10} {'% Avg':>10} {'Prob':>10} {'Risk':>10}\n")
                f.write("-"*80 + "\n")
                
                for candidate in self.trojan_candidates:
                    f.write(f"{candidate['signal']:<30} "
                           f"{candidate['transitions']:>10} "
                           f"{candidate['percentage_of_avg']:>9.2f}% "
                           f"{candidate['trojan_probability']:>9.1f}% "
                           f"{candidate['risk_level']:>10}\n")
                
                # Critical findings
                critical = [c for c in self.trojan_candidates if c['risk_level'] == 'CRITICAL']
                if critical:
                    f.write("\n" + "!"*80 + "\n")
                    f.write("CRITICAL FINDINGS - IMMEDIATE INVESTIGATION REQUIRED\n")
                    f.write("!"*80 + "\n")
                    for c in critical:
                        f.write(f"\nSignal: {c['signal']}\n")
                        f.write(f"  Transitions: {c['transitions']} ({c['percentage_of_avg']:.2f}% of average)\n")
                        f.write(f"  Trojan Probability: {c['trojan_probability']:.1f}%\n")
                        f.write(f"  Risk Level: {c['risk_level']}\n")
                        f.write(f"  Recommendation: Manual inspection of signal usage and connectivity\n")
            
            else:
                f.write("-"*80 + "\n")
                f.write("NO TROJAN CANDIDATES DETECTED\n")
                f.write("-"*80 + "\n")
                f.write("All DFF signals show normal activity levels.\n")
            
            f.write("\n" + "="*80 + "\n")
            f.write("RECOMMENDATIONS\n")
            f.write("="*80 + "\n")
            if self.trojan_candidates:
                f.write("1. Manually inspect the identified suspicious signals in the Verilog code\n")
                f.write("2. Check connectivity and control flow of flagged signals\n")
                f.write("3. Verify if low activity is intentional (e.g., error handling paths)\n")
                f.write("4. Consider extended simulation with different test vectors\n")
            else:
                f.write("1. Circuit shows normal transition patterns\n")
                f.write("2. Consider testing with different stimuli for comprehensive coverage\n")
                f.write("3. No immediate Trojan indicators detected\n")
        
        print(f"  ✓ Report saved to: {output_file}")
        
        # Console summary
        print("\n" + "="*80)
        print("DETECTION SUMMARY")
        print("="*80)
        print(f"Trojan Candidates Found: {len(self.trojan_candidates)}")
        
        if self.trojan_candidates:
            print("\nTop 5 Suspects:")
            for i, candidate in enumerate(self.trojan_candidates[:5], 1):
                print(f"  {i}. {candidate['signal']}")
                print(f"     - Transitions: {candidate['transitions']}")
                print(f"     - Activity: {candidate['percentage_of_avg']:.2f}% of average")
                print(f"     - Trojan Probability: {candidate['trojan_probability']:.1f}%")
                print(f"     - Risk: {candidate['risk_level']}")
        else:
            print("\nNo Trojan candidates detected.")
            print("All signals show normal activity patterns.")
        
        print("="*80 + "\n")
    
    def run_detection(self):
        """Run complete PCTD detection pipeline"""
        print("\n" + "="*80)
        print("PCTD HARDWARE TROJAN DETECTION")
        print("="*80)
        
        self.load_transition_data()
        self.parse_verilog()
        self.identify_suspicious_signals()
        self.analyze_trojan_candidates()
        self.generate_report()
        
        print("\n" + "="*80)
        print("DETECTION COMPLETE")
        print("="*80 + "\n")


def main():
    if len(sys.argv) < 3:
        print("Usage: py PCTD_improved.py <verilog_file> <transition_json_file>")
        print("\nExample:")
        print("  py PCTD_improved.py uart.v dff_transition_frequencies.json")
        sys.exit(1)
    
    verilog_file = sys.argv[1]
    transition_file = sys.argv[2]
    
    if not Path(verilog_file).exists():
        print(f"Error: Verilog file not found: {verilog_file}")
        sys.exit(1)
    
    if not Path(transition_file).exists():
        print(f"Error: Transition data file not found: {transition_file}")
        sys.exit(1)
    
    detector = PCTDDetector(verilog_file, transition_file)
    detector.run_detection()


if __name__ == "__main__":
    main()