def create_file_if_not_exists(file_path):
    from pathlib import Path
    Path(file_path).parent.mkdir(parents=True, exist_ok=True)
    Path(file_path).touch(exist_ok=True)


def find_files_recursively(directory:str, ext:str):
    import os
    import glob
    return [file for file in glob.iglob(os.path.join(directory, f"**/*.*.{ext}"), recursive=True)]
