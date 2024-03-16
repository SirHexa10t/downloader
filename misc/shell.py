def print_and_capture_sout(command: list):
    import subprocess

    with subprocess.Popen(command, stdout=subprocess.PIPE, text=True, bufsize=1, universal_newlines=True) as process:
        captured_output_list = []
        for line in process.stdout:
            print(line, end="")
            captured_output_list.append(line)

    captured_output = ''.join(captured_output_list)
    return captured_output
