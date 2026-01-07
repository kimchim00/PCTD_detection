"""
Complete RS232 Hardware Trojan Detection Flow
Integrates: Simulation -> Transition Extraction -> PCTD Detection
"""

import os
import subprocess
import json
import sys
from pathlib import Path
import time

# Add scripts directory to path
SCRIPT_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPT_DIR))

from extract_transitions import VCDAnalyzer
from PCTD_improved import PCTD


class RS232DetectionFlow:
    def __init__(self, design_dir, testbench_dir, work_dir, simulator='iverilog'):
        """
        design_dir: Directory with RS232 verilog files
        testbench_dir: Directory with testbench
        work_dir: Working directory for results
        simulator: 'iverilog' or 'modelsim'
        """
        self.design_dir = Path(design_dir)
        self.testbench_dir = Path(testbench_dir)
        self.work_dir = Path(work_dir)
        self.work_dir.mkdir(exist_ok=True, parents=True)
        self.simulator = simulator.lower()
        
        print(f"Design directory: {self.design_dir}")
        print(f"Testbench directory: {self.testbench_dir}")
        print(f"Work directory: {self.work_dir}")
        print(f"Simulator: {self.simulator}")

    def run_iverilog_simulation(self):
        """Run simulation using Icarus Verilog"""
        print("\n" + "="*60)
        print("STEP 1: Running Simulation with Icarus Verilog")
        print("="*60)
        
        # Find all verilog files
        design_files = list(self.design_dir.glob("*.v"))
        testbench_files = list(self.testbench_dir.glob("*.v"))
        
        if not design_files:
            print(f"Error: No .v files in {self.design_dir}")
            return False
        
        if not testbench_files:
            print(f"Error: No testbench in {self.testbench_dir}")
            return False
        
        print(f"Found {len(design_files)} design files")
        print(f"Found {len(testbench_files)} testbench files")
        
        # Prepare source list
        sources = [str(f) for f in design_files + testbench_files]
        output_file = self.work_dir / 'uart_sim'
        
        # Compile
        print("\nCompiling...")
        compile_cmd = [
            'iverilog',
            '-o', str(output_file),
            '-I', str(self.design_dir),
            '-I', str(self.testbench_dir)
        ] + sources
        
        try:
            result = subprocess.run(
                compile_cmd,
                capture_output=True,
                text=True,
                timeout=120
            )
            
            if result.returncode != 0:
                print(f"Compilation failed:\n{result.stderr}")
                return False
            
            print("✓ Compilation successful")
            
        except FileNotFoundError:
            print("Error: Icarus Verilog not found")
            print("Install: sudo apt-get install iverilog")
            print("Or download from: http://bleyer.org/icarus/")
            return False
        except Exception as e:
            print(f"Compilation error: {e}")
            return False
        
        # Run simulation
        print("\nRunning simulation...")
        try:
            result = subprocess.run(
                ['vvp', str(output_file)],
                cwd=str(self.work_dir),
                capture_output=True,
                text=True,
                timeout=120
            )
            
            print(result.stdout)
            
            # Check for VCD file
            vcd_file = self.work_dir / 'uart_sim.vcd'
            if vcd_file.exists():
                print(f"✓ Simulation complete: {vcd_file}")
                print(f"  VCD file size: {vcd_file.stat().st_size / 1024:.2f} KB")
                return True
            else:
                print("Error: VCD file not created")
                return False
                
        except subprocess.TimeoutExpired:
            print("Error: Simulation timeout (120s)")
            return False
        except Exception as e:
            print(f"Simulation error: {e}")
            return False

    def extract_transition_frequencies(self):
        """Extract transition frequencies from VCD"""
        print("\n" + "="*60)
        print("STEP 2: Extracting Transition Frequencies")
        print("="*60)
        
        vcd_file = self.work_dir / 'uart_sim.vcd'
        
        if not vcd_file.exists():
            print(f"Error: VCD file not found: {vcd_file}")
            return None
        
        analyzer = VCDAnalyzer(str(vcd_file))
        analyzer.parse_vcd()
        
        # Generate reports
        report_file = self.work_dir / 'transition_report.txt'
        json_all = self.work_dir / 'transition_frequencies.json'
        json_dff = self.work_dir / 'dff_transition_frequencies.json'
        
        frequencies, dff_signals = analyzer.generate_report(str(report_file))
        analyzer.save_json(str(json_all), str(json_dff))
        
        print(f"✓ Extracted frequencies for {len(frequencies)} signals")
        print(f"✓ Identified {len(dff_signals)} DFF signals")
        
        return str(json_dff)

    def run_pctd_detection(self, trans_freq_file, netlist_file):
        """Run PCTD detection"""
        print("\n" + "="*60)
        print("STEP 3: Running PCTD Hardware Trojan Detection")
        print("="*60)
        
        pctd = PCTD(
            str(netlist_file),
            trans_freq_file,
            threshold_trans=2**-13
        )
        
        ht_signals, time_taken = pctd.run()
        
        # Save results
        results = {
            'design': netlist_file.stem,
            'netlist_file': str(netlist_file),
            'ht_signals_detected': list(ht_signals),
            'num_ht_detected': len(ht_signals),
            'detection_time_seconds': time_taken,
            'statistics': pctd.stats,
            'timestamp': time.strftime("%Y-%m-%d %H:%M:%S")
        }
        
        results_file = self.work_dir / 'pctd_results.json'
        with open(results_file, 'w') as f:
            json.dump(results, f, indent=2)
        
        print(f"✓ Results saved: {results_file}")
        
        return results

    def generate_summary(self, results):
        """Generate summary report"""
        print("\n" + "="*60)
        print("STEP 4: Generating Summary Report")
        print("="*60)
        
        summary_file = self.work_dir / 'detection_summary.txt'
        
        with open(summary_file, 'w') as f:
            f.write("="*80 + "\n")
            f.write("HARDWARE TROJAN DETECTION SUMMARY\n")
            f.write("="*80 + "\n\n")
            
            f.write(f"Design: {results['design']}\n")
            f.write(f"Netlist: {results['netlist_file']}\n")
            f.write(f"Timestamp: {results['timestamp']}\n")
            f.write(f"Detection Time: {results['detection_time_seconds']:.2f} seconds\n\n")
            
            f.write("-"*80 + "\n")
            f.write(f"RESULT: {results['num_ht_detected']} suspicious signal(s) detected\n")
            f.write("-"*80 + "\n\n")
            
            if results['num_ht_detected'] > 0:
                f.write("SUSPICIOUS SIGNALS:\n")
                for sig in results['ht_signals_detected']:
                    f.write(f"  • {sig}\n")
                f.write("\n")
            
            stats = results['statistics']
            f.write("STATISTICS:\n")
            f.write(f"  Total Signals: {stats.get('total_signals', 'N/A')}\n")
            f.write(f"  Total Modules: {stats.get('total_modules', 'N/A')}\n")
            f.write(f"  Safe Modules: {stats.get('safe_modules', 'N/A')}\n")
            f.write(f"  Diagnostic Modules: {stats.get('diagnostic_modules', 'N/A')}\n")
            f.write(f"  Clustering Time: {stats.get('clustering_time', 0):.2f}s\n")
            f.write(f"  Total Time: {stats.get('total_time', 0):.2f}s\n\n")
            
            f.write("="*80 + "\n")
            if results['num_ht_detected'] == 0:
                f.write("CONCLUSION: No hardware trojans detected\n")
                f.write("STATUS: Design appears CLEAN ✓\n")
            else:
                f.write("CONCLUSION: Suspicious signals detected\n")
                f.write("RECOMMENDATION: Manual inspection required ⚠\n")
            f.write("="*80 + "\n")
        
        print(f"✓ Summary saved: {summary_file}")
        
        # Print to console
        print("\n")
        with open(summary_file, 'r') as f:
            print(f.read())

    def run_complete_flow(self):
        """Run complete detection flow"""
        print("\n" + "#"*80)
        print("# RS232 HARDWARE TROJAN DETECTION - COMPLETE FLOW")
        print("#"*80 + "\n")
        
        overall_start = time.time()
        
        # Step 1: Simulation
        if not self.run_iverilog_simulation():
            print("\n✗ Flow failed at simulation step")
            return None
        
        # Step 2: Extract frequencies
        trans_freq_file = self.extract_transition_frequencies()
        if not trans_freq_file:
            print("\n✗ Flow failed at frequency extraction step")
            return None
        
        # Step 3: PCTD Detection
        uart_file = self.design_dir / 'uart.v'
        if not uart_file.exists():
            print(f"Error: Main netlist not found: {uart_file}")
            return None
        
        results = self.run_pctd_detection(trans_freq_file, uart_file)
        
        # Step 4: Generate summary
        self.generate_summary(results)
        
        overall_time = time.time() - overall_start
        
        print("\n" + "#"*80)
        print(f"# FLOW COMPLETED in {overall_time:.2f} seconds")
        print("#"*80 + "\n")
        
        print(f"✓ All results saved in: {self.work_dir}")
        print(f"✓ Key files:")
        print(f"  - detection_summary.txt (main report)")
        print(f"  - pctd_results.json (detailed results)")
        print(f"  - transition_report.txt (signal analysis)")
        
        return results


def main():
    """Main entry point"""
    
    # Configuration - تنظیمات
    PROJECT_ROOT = Path(r"C:\PCTD_Project")
    DESIGN_DIR = PROJECT_ROOT / "design"
    TESTBENCH_DIR = PROJECT_ROOT / "testbench"
    RESULTS_DIR = PROJECT_ROOT / "results"
    
    print("="*80)
    print("RS232 Hardware Trojan Detection")
    print("="*80)
    print(f"Project root: {PROJECT_ROOT}")
    print(f"Design dir: {DESIGN_DIR}")
    print(f"Testbench dir: {TESTBENCH_DIR}")
    print(f"Results dir: {RESULTS_DIR}")
    print("="*80)
    
    # Verify directories exist
    if not DESIGN_DIR.exists():
        print(f"\n✗ Error: Design directory not found: {DESIGN_DIR}")
        print("Please create the directory and add your RS232 files")
        return
    
    if not TESTBENCH_DIR.exists():
        print(f"\n✗ Error: Testbench directory not found: {TESTBENCH_DIR}")
        print("Please create the directory and add tb_uart.v")
        return
    
    # Check for required files
    required_design_files = ['uart.v', 'u_rec.v', 'u_xmit.v', 'inc.h']
    missing_files = []
    for fname in required_design_files:
        if not (DESIGN_DIR / fname).exists():
            missing_files.append(fname)
    
    if missing_files:
        print(f"\n⚠ Warning: Missing design files: {', '.join(missing_files)}")
        print("Proceeding anyway...")
    
    if not (TESTBENCH_DIR / 'tb_uart.v').exists():
        print(f"\n✗ Error: Testbench not found: {TESTBENCH_DIR / 'tb_uart.v'}")
        return
    
    # Create and run flow
    flow = RS232DetectionFlow(
        DESIGN_DIR,
        TESTBENCH_DIR,
        RESULTS_DIR,
        simulator='iverilog'
    )
    
    results = flow.run_complete_flow()
    
    if results:
        print("\n" + "="*80)
        print("SUCCESS!")
        print("="*80)
        if results['num_ht_detected'] == 0:
            print("✓ No hardware trojans detected")
            print("✓ Design appears CLEAN")
        else:
            print(f"⚠ {results['num_ht_detected']} suspicious signal(s) detected")
            print("⚠ Please review the detection report")
    else:
        print("\n" + "="*80)
        print("FAILED")
        print("="*80)
        print("Please check error messages above")


if __name__ == "__main__":
    main()
