"""Conservative Windows memory admission checks for MART studies."""
from experiment_05a import available_ram_gib


def validate_grid(size: int, factor: int, allow_large: bool = False,
                  min_free_ram_gib: float = 4.) -> float | None:
    if size < 4 or factor < 2 or size > 32 or size * factor > 64:
        raise ValueError("05B grid limits: 4 <= coarse size <= 32, factor >= 2, fine size <= 64")
    if (size > 16 or size * factor > 32) and not allow_large:
        raise ValueError("Large grid requires --allow-large (and sufficient available RAM)")
    if min_free_ram_gib < 4.:
        raise ValueError("05B does not permit reducing the 4 GiB large-run RAM floor")
    if size > 16 or size * factor > 32:
        free = available_ram_gib()
        if free < min_free_ram_gib:
            raise ValueError(f"Only {free:.2f} GiB free RAM; {min_free_ram_gib:.2f} GiB required")
        return free
    return None
