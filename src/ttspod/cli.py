"""sample CLI wrapper"""
# optional system certificate trust
try:
    import truststore
    truststore.inject_into_ssl()
except ImportError:
    pass

import ttspod.app

def main():
    """main python entrypoint"""
    ttspod.app.main()
