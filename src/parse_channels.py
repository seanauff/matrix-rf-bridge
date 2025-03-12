import re
import logging

def parse_channels(config_path):
    """
    Parse the channels from rtl_airband.conf and return a list of frequencies in Hz.
    
    Args:
        config_path (str): Path to the configuration file.
    
    Returns:
        list: List of frequencies in Hertz (integers).
    """
    frequencies = []
    
    try:
        with open(config_path, 'r') as f:
            content = f.read()
        
        # Locate the channels section
        channels_start = content.find("channels:")
        if channels_start == -1:
            logging.warning("No 'channels:' section found in config file.")
            return []
        
        paren_start = content.find("(", channels_start)
        paren_end = content.find(");", paren_start)
        if paren_start == -1 or paren_end == -1:
            logging.warning("Invalid channels section format.")
            return []
        
        channels_content = content[paren_start + 1:paren_end]
        
        # Find all frequency lines
        freq_matches = re.findall(r'freq\s*=\s*(.*?);', channels_content)
        
        for match in freq_matches:
            try:
                freq_hz = parse_frequency(match)
                frequencies.append(freq_hz)
            except ValueError as e:
                logging.warning(f"Failed to parse frequency: {match} - {e}")
    
    except FileNotFoundError:
        logging.error(f"Config file not found: {config_path}")
        return []
    except Exception as e:
        logging.error(f"Error reading config file: {e}")
        return []
    
    return frequencies

def parse_frequency(value_str):
    """
    Parse a frequency string into an integer in Hertz.
    
    Args:
        value_str (str): The frequency value (e.g., '121500000', '121.5', '"121.5M"').
    
    Returns:
        int: Frequency in Hertz.
    
    Raises:
        ValueError: If the frequency format is invalid.
    """
    value_str = value_str.strip()
    
    # Check if the value is a quoted string
    if value_str.startswith('"') and value_str.endswith('"'):
        # Remove quotes
        value_str = value_str[1:-1]
        # Match numeric part and optional multiplier (e.g., '121.5M', '121500k', '121500000')
        match = re.match(r'(\d+\.?\d*)([kKmMgG]?)$', value_str)
        if not match:
            raise ValueError(f"Invalid frequency string: {value_str}")
        
        num_part = float(match.group(1))  # Convert numeric part to float
        multiplier = match.group(2).lower() if match.group(2) else ''
        
        # Apply multiplier
        if multiplier == 'k':
            return int(num_part * 1000)
        elif multiplier == 'm':
            return int(num_part * 1000000)
        elif multiplier == 'g':
            return int(num_part * 1000000000)
        else:
            return int(num_part)  # No multiplier, assume Hz
    else:
        # It's a number (not quoted)
        if '.' in value_str:
            # Float in MHz
            return int(float(value_str) * 1000000)
        else:
            # Integer in Hz
            return int(value_str)