import platform


def cpu_model():
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
            r'HARDWARE\DESCRIPTION\System\CentralProcessor\0') as key:
            return winreg.QueryValueEx(key,'ProcessorNameString')[0].strip()
    except (ImportError,OSError):
        return platform.processor() or platform.machine()
