#!/usr/bin/env python3
"""
Automated Trojan Detection for Multiple RS232 Benchmarks
Tests all benchmark variants and generates comparative report
"""

import os
import sys
import json
import zipfile
import shutil
from pathlib import Path
from datetime import datetime

# Add current directory to path
SCRIPT_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPT_DIR))

try:
    from extract_transitions import VCDAnalyzer
    from PCTD_improved import PCTDDetector
except ImportError as e:
    print(f"Error importing modules: {e}")
    print("Make sure extract_transitions.py and PCTD_improved.py are in the same directory")
    sys.exit(1)


class BenchmarkTester:
    def __init__(self, benchmarks_dir, work_dir):
        self.benchmarks_dir = Path(benchmarks_dir)
        self.work_dir = Path(work_dir)
        self.work_dir.mkdir(exist_ok=True, parents=True)
        
        self.results = {}
        
    def extract_benchmark(self, zip_file, extract_to):
        """Extract benchmark zip file"""
        print(f"  Extracting: {zip_file.name}")
        
        try:
            with zipfile.ZipFile(zip_file, 'r') as zip_ref:
                zip_ref.extractall(extract_to)
            
            # Find the actual source directory
            src_dirs = list(extract_to.glob("**/src"))
            if src_dirs:
                return src_dirs[0]
            else:
                # Maybe files are in root
                return extract_to
                
        except Exception as e:
            print(f"  Error extracting: {e}")
            return None
    
    def find_vcd_file(self, benchmark_name):
        """Find VCD file for benchmark"""
        # Common locations
        possible_locations = [
            self.work_dir / f"{benchmark_name}_sim.vcd",
            Path.home() / "Desktop" / f"{benchmark_name}.vcd",
            Path.home() / "AppData" / "Roaming" / "Xilinx" / "Vivado" / "uart_simulation.vcd",
        ]
        
        for vcd_path in possible_locations:
            if vcd_path.exists():
                return vcd_path
        
        return None
    
    def analyze_benchmark(self, benchmark_name, src_dir, vcd_file):
        """Analyze a single benchmark"""
        print(f"\n{'='*80}")
        print(f"Analyzing: {benchmark_name}")
        print(f"{'='*80}")
        
        result = {
            'benchmark': benchmark_name,
            'timestamp': datetime.now().isoformat(),
            'status': 'unknown',
            'vcd_file': str(vcd_file) if vcd_file else None,
            'src_dir': str(src_dir),
        }
        
        # Find main Verilog file
        uart_file = src_dir / "uart.v"
        if not uart_file.exists():
            print(f"  Error: uart.v not found in {src_dir}")
            result['status'] = 'error'
            result['error'] = 'uart.v not found'
            return result
        
        # Check if VCD exists
        if not vcd_file or not vcd_file.exists():
            print(f"  Warning: VCD file not found")
            print(f"  You need to run simulation first for {benchmark_name}")
            result['status'] = 'no_vcd'
            result['error'] = 'VCD file not found - run simulation first'
            return result
        
        print(f"  VCD file: {vcd_file}")
        print(f"  Source: {uart_file}")
        
        # Step 1: Extract transitions
        print(f"\n[1/2] Extracting transition frequencies...")
        try:
            analyzer = VCDAnalyzer(str(vcd_file))
            analyzer.parse_vcd()
            
            # Save results in benchmark-specific directory
            bench_dir = self.work_dir / benchmark_name
            bench_dir.mkdir(exist_ok=True)
            
            report_file = bench_dir / 'transition_report.txt'
            json_all = bench_dir / 'transition_frequencies.json'
            json_dff = bench_dir / 'dff_transition_frequencies.json'
            
            frequencies, dff_signals = analyzer.generate_report(str(report_file))
            analyzer.save_json(str(json_all), str(json_dff))
            
            result['total_signals'] = len(frequencies)
            result['dff_signals'] = len(dff_signals)
            result['avg_transitions'] = sum(analyzer.transitions.values()) / len(analyzer.transitions) if analyzer.transitions else 0
            
            print(f"  Total signals: {result['total_signals']}")
            print(f"  DFF signals: {result['dff_signals']}")
            print(f"  Avg transitions: {result['avg_transitions']:.2f}")
            
        except Exception as e:
            print(f"  Error extracting transitions: {e}")
            result['status'] = 'error'
            result['error'] = str(e)
            return result
        
        # Step 2: PCTD Detection
        print(f"\n[2/2] Running PCTD detection...")
        try:
            detector = PCTDDetector(str(uart_file), str(json_dff))
            detector.load_transition_data()
            detector.parse_verilog()
            detector.identify_suspicious_signals()
            detector.analyze_trojan_candidates()
            
            detection_report = bench_dir / 'pctd_detection_report.txt'
            detector.generate_report(str(detection_report))
            
            result['status'] = 'success'
            result['suspicious_signals'] = len(detector.suspicious_signals)
            result['trojan_candidates'] = len(detector.trojan_candidates)
            result['detection_report'] = str(detection_report)
            
            # Extract top suspects
            result['top_suspects'] = []
            for candidate in detector.trojan_candidates[:5]:
                result['top_suspects'].append({
                    'signal': candidate['signal'],
                    'transitions': candidate['transitions'],
                    'percentage_of_avg': candidate['percentage_of_avg'],
                    'risk_level': candidate['risk_level']
                })
            
            print(f"  Suspicious signals: {result['suspicious_signals']}")
            print(f"  Trojan candidates: {result['trojan_candidates']}")
            
        except Exception as e:
            print(f"  Error in PCTD detection: {e}")
            result['status'] = 'error'
            result['error'] = str(e)
            return result
        
        return result
    
    def generate_comparison_report(self):
        """Generate comparative analysis report"""
        print(f"\n{'='*80}")
        print("Generating Comparison Report")
        print(f"{'='*80}")
        
        report_file = self.work_dir / 'comparison_report.txt'
        json_file = self.work_dir / 'comparison_results.json'
        
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write("="*80 + "\n")
            f.write("RS232 BENCHMARK TROJAN DETECTION - COMPARISON REPORT\n")
            f.write("="*80 + "\n\n")
            f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Total benchmarks tested: {len(self.results)}\n\n")
            
            # Summary table
            f.write("-"*80 + "\n")
            f.write("SUMMARY TABLE\n")
            f.write("-"*80 + "\n")
            f.write(f"{'Benchmark':<20} {'Status':<12} {'DFFs':<8} {'Suspects':<10} {'Trojans':<10}\n")
            f.write("-"*80 + "\n")
            
            for bench_name, result in sorted(self.results.items()):
                status = result.get('status', 'unknown')
                dffs = result.get('dff_signals', 'N/A')
                suspects = result.get('suspicious_signals', 'N/A')
                trojans = result.get('trojan_candidates', 'N/A')
                
                f.write(f"{bench_name:<20} {status:<12} {str(dffs):<8} {str(suspects):<10} {str(trojans):<10}\n")
            
            # Detailed results
            f.write("\n" + "="*80 + "\n")
            f.write("DETAILED RESULTS\n")
            f.write("="*80 + "\n\n")
            
            for bench_name, result in sorted(self.results.items()):
                f.write("-"*80 + "\n")
                f.write(f"BENCHMARK: {bench_name}\n")
                f.write("-"*80 + "\n")
                
                if result['status'] == 'success':
                    f.write(f"Status: SUCCESS\n")
                    f.write(f"Total Signals: {result['total_signals']}\n")
                    f.write(f"DFF Signals: {result['dff_signals']}\n")
                    f.write(f"Average Transitions: {result['avg_transitions']:.2f}\n")
                    f.write(f"Suspicious Signals: {result['suspicious_signals']}\n")
                    f.write(f"Trojan Candidates: {result['trojan_candidates']}\n\n")
                    
                    if result['top_suspects']:
                        f.write("Top Suspects:\n")
                        for i, suspect in enumerate(result['top_suspects'], 1):
                            f.write(f"  {i}. {suspect['signal']}\n")
                            f.write(f"     Transitions: {suspect['transitions']}\n")
                            f.write(f"     Activity: {suspect['percentage_of_avg']:.2f}% of average\n")
                            f.write(f"     Risk: {suspect['risk_level']}\n")
                    else:
                        f.write("No suspicious signals detected.\n")
                    
                    f.write(f"\nDetailed report: {result['detection_report']}\n")
                    
                elif result['status'] == 'no_vcd':
                    f.write(f"Status: NO VCD FILE\n")
                    f.write(f"Error: {result.get('error', 'Unknown')}\n")
                    f.write(f"Action required: Run simulation for this benchmark\n")
                    
                else:
                    f.write(f"Status: ERROR\n")
                    f.write(f"Error: {result.get('error', 'Unknown')}\n")
                
                f.write("\n")
            
            f.write("="*80 + "\n")
            f.write("RECOMMENDATIONS\n")
            f.write("="*80 + "\n")
            
            success_count = sum(1 for r in self.results.values() if r['status'] == 'success')
            trojan_count = sum(1 for r in self.results.values() 
                             if r['status'] == 'success' and r.get('trojan_candidates', 0) > 0)
            
            f.write(f"1. Successfully analyzed: {success_count}/{len(self.results)} benchmarks\n")
            f.write(f"2. Benchmarks with detected trojans: {trojan_count}\n")
            f.write(f"3. For benchmarks without VCD files, run simulations first\n")
            f.write(f"4. Review detailed reports for each benchmark in subdirectories\n")
        
        # Save JSON
        with open(json_file, 'w') as f:
            json.dump(self.results, f, indent=2)
        
        print(f"  Comparison report: {report_file}")
        print(f"  JSON results: {json_file}")
        
        # Print summary to console
        print("\n" + "="*80)
        print("COMPARISON SUMMARY")
        print("="*80)
        print(f"{'Benchmark':<20} {'Status':<12} {'Trojans':<10}")
        print("-"*80)
        
        for bench_name, result in sorted(self.results.items()):
            status = result.get('status', 'unknown')
            trojans = result.get('trojan_candidates', 'N/A')
            print(f"{bench_name:<20} {status:<12} {str(trojans):<10}")
        
        print("="*80 + "\n")
    
    def run_all_benchmarks(self):
        """Run detection on all available benchmarks"""
        print("\n" + "#"*80)
        print("# RS232 BENCHMARK SUITE - TROJAN DETECTION")
        print("#"*80 + "\n")
        
        # Find all zip files
        zip_files = list(self.benchmarks_dir.glob("RS232-*.zip"))
        
        if not zip_files:
            print(f"No benchmark zip files found in: {self.benchmarks_dir}")
            print("Looking for files matching pattern: RS232-*.zip")
            return
        
        print(f"Found {len(zip_files)} benchmark(s):")
        for zf in zip_files:
            print(f"  - {zf.name}")
        
        # Process each benchmark
        for zip_file in sorted(zip_files):
            benchmark_name = zip_file.stem  # e.g., "RS232-T100"
            
            # Extract benchmark
            extract_dir = self.work_dir / benchmark_name / "extracted"
            extract_dir.mkdir(exist_ok=True, parents=True)
            
            src_dir = self.extract_benchmark(zip_file, extract_dir)
            if not src_dir:
                self.results[benchmark_name] = {
                    'benchmark': benchmark_name,
                    'status': 'error',
                    'error': 'Failed to extract benchmark'
                }
                continue
            
            # Try to find VCD file
            vcd_file = self.find_vcd_file(benchmark_name)
            
            # Analyze
            result = self.analyze_benchmark(benchmark_name, src_dir, vcd_file)
            self.results[benchmark_name] = result
        
        # Generate comparison report
        self.generate_comparison_report()
        
        print("\n" + "#"*80)
        print("# TESTING COMPLETE")
        print("#"*80)
        print(f"\nAll results saved in: {self.work_dir}")


def main():
    """Main entry point"""
    
    # Configuration
    BENCHMARKS_DIR = Path(r"C:\Users\kimia\Downloads")
    WORK_DIR = Path(r"C:\Users\kimia\Desktop\vhdl_PCTD\benchmark_results")
    
    print("="*80)
    print("RS232 Benchmark Trojan Detection Suite")
    print("="*80)
    print(f"Benchmarks directory: {BENCHMARKS_DIR}")
    print(f"Results directory: {WORK_DIR}")
    print("="*80 + "\n")
    
    if not BENCHMARKS_DIR.exists():
        print(f"Error: Benchmarks directory not found: {BENCHMARKS_DIR}")
        sys.exit(1)
    
    # Create tester and run
    tester = BenchmarkTester(BENCHMARKS_DIR, WORK_DIR)
    tester.run_all_benchmarks()
    
    print("\nDONE! Check the results directory for detailed reports.")


if __name__ == "__main__":
    main()