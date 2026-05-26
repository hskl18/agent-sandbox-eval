def parse_env(lines):
    return dict(line.split("=") for line in lines)

