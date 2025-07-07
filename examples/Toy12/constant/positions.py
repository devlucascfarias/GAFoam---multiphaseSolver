import numpy as np

# Domain bounds
x_min, x_max = 0.0, 0.05
y_min, y_max = 0.0, 0.15
z_val = 0.005  # For 2D with Z thickness 0.01

# Cell size
dx, dy = 0.001, 0.001

# Number of points
nx = int((x_max - x_min) / dx)
ny = int((y_max - y_min) / dy)

# Generate positions at cell centers
x_vals = np.linspace(x_min + dx/2, x_max - dx/2, nx)
y_vals = np.linspace(y_min + dy/2, y_max - dy/2, ny)

with open("positions.dat", "w") as f:
    f.write("""/*--------------------------------*- C++ -*----------------------------------*\\
| =========                 |
| \\      /  F ield         | OpenFOAM: The Open Source CFD Toolbox
|  \\    /   O peration     | Website:  https://openfoam.org
|   \\  /    A nd           | Version:  12
|    \\/     M anipulation  |
\\*---------------------------------------------------------------------------*/
FoamFile
{
    version     2.0;
    format      ascii;
    class       vectorField;
    location    "constant";
    object      positions;
}
// * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * //

(
""")
    for x in x_vals:
        for y in y_vals:
            f.write(f"    ({x:.6f} {y:.6f} {z_val:.6f})\n")
    f.write(")\n\n// ************************************************************************* //\n")

