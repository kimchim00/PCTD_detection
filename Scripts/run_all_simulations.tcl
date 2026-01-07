# Vivado TCL Script - Batch Simulation for All RS232 Benchmarks
# Run this in Vivado TCL Console or as batch script

# Configuration
set work_dir "C:/Users/kimia/Desktop/vhdl_PCTD/benchmark_results"
set benchmarks_dir "C:/Users/kimia/Downloads"
set tb_file "C:/Users/kimia/project_1/project_1.srcs/sources_1/new/tb_uart_clean.v"

# List of benchmarks to simulate
set benchmarks [list \
    "RS232-T100" \
    "RS232-T200" \
    "RS232-T500" \
    "RS232-T700" \
    "RS232-T1000" \
    "RS232-T1100" \
]

puts "========================================================================"
puts "VIVADO BATCH SIMULATION - RS232 BENCHMARKS"
puts "========================================================================"
puts "Work directory: $work_dir"
puts "Benchmarks: [llength $benchmarks]"
puts "========================================================================"

# Counter for results
set success_count 0
set error_count 0

# Process each benchmark
foreach bench $benchmarks {
    puts "\n"
    puts "========================================================================"
    puts "SIMULATING: $bench"
    puts "========================================================================"
    
    # Find source directory
    set extracted_dir "$work_dir/$bench/extracted"
    
    # Try different possible locations
    set src_dirs [list \
        "$extracted_dir/$bench/src" \
        "$extracted_dir/src" \
        "$extracted_dir/$bench" \
        "$extracted_dir" \
    ]
    
    set src_dir ""
    foreach dir $src_dirs {
        if {[file exists "$dir/uart.v"]} {
            set src_dir $dir
            break
        }
    }
    
    if {$src_dir eq ""} {
        puts "ERROR: Cannot find uart.v for $bench"
        puts "Searched in:"
        foreach dir $src_dirs {
            puts "  - $dir"
        }
        incr error_count
        continue
    }
    
    puts "Source directory: $src_dir"
    
    # Check for required files
    set required_files [list "uart.v" "u_rec.v" "u_xmit.v"]
    set missing_files [list]
    
    foreach file $required_files {
        if {![file exists "$src_dir/$file"]} {
            lappend missing_files $file
        }
    }
    
    if {[llength $missing_files] > 0} {
        puts "ERROR: Missing files: $missing_files"
        incr error_count
        continue
    }
    
    # Close any existing project
    catch {close_project}
    
    # Create temporary project for this benchmark
    set proj_name "${bench}_sim"
    set proj_dir "$work_dir/$bench/vivado_project"
    
    # Clean up old project if exists
    if {[file exists $proj_dir]} {
        file delete -force $proj_dir
    }
    
    # Create project
    puts "Creating project: $proj_name"
    create_project $proj_name $proj_dir -part xc7a35tcpg236-1 -force
    
    # Add source files
    puts "Adding source files..."
    add_files -fileset sources_1 [list \
        "$src_dir/uart.v" \
        "$src_dir/u_rec.v" \
        "$src_dir/u_xmit.v" \
    ]
    
    # Add testbench
    if {[file exists $tb_file]} {
        puts "Adding testbench: $tb_file"
        add_files -fileset sim_1 $tb_file
        set_property top tb_uart [get_filesets sim_1]
    } else {
        puts "WARNING: Testbench not found: $tb_file"
        puts "Using default testbench if available"
    }
    
    # Update compile order
    update_compile_order -fileset sources_1
    update_compile_order -fileset sim_1
    
    # Set simulation properties
    set_property -name {xsim.simulate.runtime} -value {50ms} -objects [get_filesets sim_1]
    
    # Launch simulation
    puts "Launching simulation..."
    
    if {[catch {
        launch_simulation
        
        # Wait for simulation to be ready
        after 3000
        
        # Open VCD file
        set vcd_file "$work_dir/$bench/${bench}_sim.vcd"
        puts "Opening VCD file: $vcd_file"
        
        catch {close_vcd}
        open_vcd $vcd_file
        
        # Log all signals
        puts "Logging signals..."
        log_vcd [get_objects -r /*]
        
        # Run simulation
        puts "Running simulation for 50ms..."
        restart
        run 50ms
        
        # Close VCD
        puts "Closing VCD file..."
        close_vcd
        
        # Verify VCD was created
        if {[file exists $vcd_file]} {
            set file_size [file size $vcd_file]
            puts "SUCCESS: VCD file created ($file_size bytes)"
            incr success_count
        } else {
            puts "ERROR: VCD file was not created"
            incr error_count
        }
        
        # Close simulation
        close_sim
        
    } error_msg]} {
        puts "ERROR during simulation: $error_msg"
        incr error_count
    }
    
    # Close project
    catch {close_project}
    
    puts "========================================================================\n"
}

# Final summary
puts "\n"
puts "========================================================================"
puts "BATCH SIMULATION COMPLETE"
puts "========================================================================"
puts "Total benchmarks: [llength $benchmarks]"
puts "Successful: $success_count"
puts "Failed: $error_count"
puts "========================================================================"

# List created VCD files
puts "\nCreated VCD files:"
foreach bench $benchmarks {
    set vcd_file "$work_dir/$bench/${bench}_sim.vcd"
    if {[file exists $vcd_file]} {
        set size [expr {[file size $vcd_file] / 1024.0}]
        puts "  OK  - $bench ([format %.2f $size] KB)"
    } else {
        puts "  MISSING - $bench"
    }
}

puts "\nNext step: Run 'py test_all_benchmarks.py' to detect trojans"
puts "========================================================================"