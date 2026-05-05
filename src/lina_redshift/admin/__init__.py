"""Admin-only operations on the Redshift workgroup.

These are NOT regular migrations — they manage roles and grants that the
chat runtime depends on but that aren't part of the schema lifecycle.
"""
