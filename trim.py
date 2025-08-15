"""
Joystick Gremlin Trim Plugin - Multi-Instance Version
Supports multiple independent trim axes
"""

import gremlin
from gremlin.user_plugin import *
import uuid

# GUI CONFIGURATION VARIABLES
mode = ModeVariable(
    "Mode",
    "The mode in which this trim mapping will be active"
)

physical_axis = PhysicalInputVariable(
    "Physical Axis",
    "The physical joystick axis to apply trim to",
    [gremlin.common.InputType.JoystickAxis]
)

output_vjoy = VirtualInputVariable(
    "Output Axis",
    "The vJoy axis where the trimmed result will be sent",
    [gremlin.common.InputType.JoystickAxis]
)

trim_up_button = PhysicalInputVariable(
    "Trim Up Button",
    "Button that increases trim",
    [gremlin.common.InputType.JoystickButton]
)

trim_down_button = PhysicalInputVariable(
    "Trim Down Button", 
    "Button that decreases trim",
    [gremlin.common.InputType.JoystickButton]
)

trim_increment = FloatVariable(
    "Trim Increment",
    "Amount to change trim per button press",
    0.01,
    0.001,
    0.1
)

trim_sensitivity = FloatVariable(
    "Trim Sensitivity",
    "Multiplier for trim effect (1.0 = normal)",
    1.0,
    0.1,
    3.0
)

enable_scaled_trim = BoolVariable(
    "Enable scaled trim mode",
    "Map full physical axis range to remaining output range after trim",
    True
)

auto_center_on_init = BoolVariable(
    "Auto-center trim on start",
    "Reset trim to center (0) when plugin starts",
    True
)

enable_debug = BoolVariable(
    "Enable debug output",
    "Show trim values in the console",
    True
)

reset_button = PhysicalInputVariable(
    "Reset Button (Optional)",
    "Button to instantly reset trim to center",
    [gremlin.common.InputType.JoystickButton]
)


# INSTANCE-SPECIFIC STATE
# Each instance gets its own unique ID and state
class TrimInstance:
    def __init__(self, instance_id):
        self.id = instance_id
        self.current_trim_value = 0.0
        self.current_trim_offset = 0.0
        self.physical_value = 0.0
        self.vjoy_proxy = None
        
    def debug_log(self, message):
        """Helper function for debug output"""
        if enable_debug.value:
            # Include instance info in debug output
            axis_name = "Unknown"
            if physical_axis.value:
                if isinstance(physical_axis.value, dict):
                    axis_name = f"Axis {physical_axis.value.get('input_id', '?')}"
                else:
                    axis_name = f"Axis {getattr(physical_axis.value, 'input_id', '?')}"
            gremlin.util.log(f"[Trim-{axis_name}] {message}")
    
    def calculate_trimmed_output(self, physical, trim_offset):
        """Calculate the output value based on physical input and trim"""
        if enable_scaled_trim.value:
            # Scaled trim mode
            if physical >= 0:
                if trim_offset >= 0:
                    remaining_range = 1.0 - trim_offset
                    if remaining_range > 0.01:
                        return trim_offset + (physical * remaining_range)
                    else:
                        return 1.0
                else:
                    return trim_offset + (physical * (1.0 - trim_offset))
            else:
                if trim_offset <= 0:
                    remaining_range = -1.0 - trim_offset
                    if abs(remaining_range) > 0.01:
                        return trim_offset + (physical * abs(remaining_range))
                    else:
                        return -1.0
                else:
                    return trim_offset + (physical * (1.0 + trim_offset))
        else:
            # Simple addition mode
            return physical + trim_offset
    
    def update_output(self):
        """Update the output axis with current values"""
        if not output_vjoy.value or not self.vjoy_proxy:
            return
            
        # Calculate output
        output = self.calculate_trimmed_output(self.physical_value, self.current_trim_offset)
        output = max(-1.0, min(1.0, output))  # Clamp to valid range
        
        # Write to output axis
        try:
            if isinstance(output_vjoy.value, dict):
                device_id = output_vjoy.value.get('device_id')
                input_id = output_vjoy.value.get('input_id')
            else:
                device_id = getattr(output_vjoy.value, 'device_id', None)
                input_id = getattr(output_vjoy.value, 'input_id', None)
                
            if device_id and input_id:
                self.vjoy_proxy[device_id].axis(input_id).value = output
                self.debug_log(f"Output: {output:.3f} (Physical: {self.physical_value:.3f}, Trim: {self.current_trim_offset:.3f})")
        except Exception as e:
            self.debug_log(f"ERROR writing output: {e}")
    
    def adjust_trim(self, delta):
        """Adjust trim by the specified amount"""
        # Update trim value
        self.current_trim_value += delta
        self.current_trim_value = max(-1.0, min(1.0, self.current_trim_value))  # Clamp to -1 to +1
        
        # Apply sensitivity
        self.current_trim_offset = self.current_trim_value * trim_sensitivity.value
        
        self.debug_log(f"Trim adjusted to {self.current_trim_offset:.3f} (raw: {self.current_trim_value:.3f})")
        
        # Update output immediately
        self.update_output()
    
    def reset_trim(self):
        """Reset trim to center (0)"""
        self.current_trim_value = 0.0
        self.current_trim_offset = 0.0
        
        self.debug_log("Trim reset to center")
        self.update_output()


# Create a unique instance for this plugin instance
instance_id = str(uuid.uuid4())
trim_instance = TrimInstance(instance_id)


# Create decorator for physical axis
if hasattr(physical_axis, 'create_decorator') and hasattr(mode, 'value') and mode.value:
    try:
        decorator = physical_axis.create_decorator(mode.value)
        
        @decorator.axis(physical_axis.input_id)
        def on_physical_axis(event, vjoy, instance=trim_instance):
            instance.vjoy_proxy = vjoy
            instance.physical_value = event.value
            instance.update_output()
            
        trim_instance.debug_log("Physical axis decorator created")
    except Exception as e:
        trim_instance.debug_log(f"ERROR creating physical decorator: {e}")


# Create decorator for trim up button
if trim_up_button.value and hasattr(mode, 'value') and mode.value:
    try:
        trim_up_decorator = trim_up_button.create_decorator(mode.value)
        
        @trim_up_decorator.button(trim_up_button.input_id)
        def on_trim_up(event, vjoy, instance=trim_instance):
            if event.is_pressed:
                instance.vjoy_proxy = vjoy
                instance.adjust_trim(trim_increment.value)
                
        trim_instance.debug_log("Trim up button decorator created")
    except Exception as e:
        trim_instance.debug_log(f"ERROR creating trim up decorator: {e}")


# Create decorator for trim down button
if trim_down_button.value and hasattr(mode, 'value') and mode.value:
    try:
        trim_down_decorator = trim_down_button.create_decorator(mode.value)
        
        @trim_down_decorator.button(trim_down_button.input_id)
        def on_trim_down(event, vjoy, instance=trim_instance):
            if event.is_pressed:
                instance.vjoy_proxy = vjoy
                instance.adjust_trim(-trim_increment.value)
                
        trim_instance.debug_log("Trim down button decorator created")
    except Exception as e:
        trim_instance.debug_log(f"ERROR creating trim down decorator: {e}")


# Create decorator for reset button if configured
if reset_button.value and hasattr(mode, 'value') and mode.value:
    try:
        reset_decorator = reset_button.create_decorator(mode.value)
        
        @reset_decorator.button(reset_button.input_id)
        def on_reset(event, vjoy, instance=trim_instance):
            if event.is_pressed:
                instance.vjoy_proxy = vjoy
                instance.reset_trim()
                
        trim_instance.debug_log("Reset button decorator created")
    except Exception as e:
        trim_instance.debug_log(f"ERROR creating reset decorator: {e}")


def plugin_init():
    """Called when plugin is activated"""
    global trim_instance
    
    trim_instance.physical_value = 0.0
    
    if auto_center_on_init.value:
        trim_instance.current_trim_value = 0.0
        trim_instance.current_trim_offset = 0.0
        trim_instance.debug_log("Plugin initialized - trim centered")
    else:
        trim_instance.debug_log("Plugin initialized - trim retained")


"""
MULTI-INSTANCE SETUP:
1. Add this plugin once for each axis you want to trim
2. Each instance maintains its own independent trim value
3. Debug messages show which axis they're for

Example for multiple axes:
- Instance 1: Pitch axis → Trim buttons 1&2 → Output vJoy 1 Axis 1
- Instance 2: Roll axis → Trim buttons 3&4 → Output vJoy 1 Axis 2  
- Instance 3: Throttle → Trim buttons 5&6 → Output vJoy 1 Axis 3
"""
