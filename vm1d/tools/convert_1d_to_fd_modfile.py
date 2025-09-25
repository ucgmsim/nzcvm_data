#!/usr/bin/env python3
"""
Simple conversion script using existing VelocityModel1D class.
"""

import argparse
from pathlib import Path
from velocity_modelling.velocity1d import VelocityModel1D, write_velocity_model_1d_plain_text
import pandas as pd


def simple_convert(input_file: Path, output_file: Path):
    """Simple conversion without resampling."""
    model = VelocityModel1D(input_file)

    df = pd.DataFrame({
        'Vp': model.vp,
        'Vs': model.vs,
        'rho': model.rho,
        'Qp': model.qp,
        'Qs': model.qs,
        'bottom_depth': model.bottom_depth,
        'width': model.width,
        'top_depth': model.top_depth
    })

    write_velocity_model_1d_plain_text(df, output_file)
    print(f"Converted {input_file} to {output_file}")


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('input_file')
    parser.add_argument('output_file')
    args = parser.parse_args()
    simple_convert(Path(args.input_file), Path(args.output_file))