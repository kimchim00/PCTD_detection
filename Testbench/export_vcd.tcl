# export_vcd.tcl - Export VCD file from Vivado simulation

# Open simulation if not already open
if {[current_sim] == ""} {
    launch_simulation
}

# Reset simulation
restart

# Open VCD file for writing
set vcd_file "uart_simulation.vcd"
open_vcd $vcd_file

# Log all signals
log_vcd [get_objects -r /*]

# Run simulation for longer time (50ms = 50,000,000 ns)
run 50ms

# Close VCD file
close_vcd

# Save waveform database
save_wave_config uart_waveform.wcfg

puts "================================"
puts "VCD Export Complete!"
puts "VCD file: $vcd_file"
puts "================================"

# Optional: Close simulation
# close_sim