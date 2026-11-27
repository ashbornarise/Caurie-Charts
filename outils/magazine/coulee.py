

def coulee(k, total, fin=False):
    """Coulée liquide verticale, large, aux bords irréguliers. Entre en haut et sort en bas à x = 16 mm avec la même
    largeur (raccord exact d'une page à l'autre). Une page sur trois, elle sort du cadre par la gauche puis revient ;
    une autre, elle gonfle en poche (15/11/2026)."""
    import math, random
    rnd = random.Random(1000 + k)
    ph = [rnd.uniform(0, 6.28) for _ in range(8)]
    gouttes = [(rnd.uniform(40, 250), rnd.uniform(1.8, 3.6)) for _ in range(3)]
    bas = 252 if fin else 297
    ys = [i * 1.5 for i in range(int(bas / 1.5) + 1)]
    ym = rnd.uniform(90, 200)
    gauche, droite, reflet = [], [], []
    for y in ys:
        e_ = math.sin(math.pi * min(y, 297) / 297) ** 0.8
        sortie = -26 * math.exp(-((y - ym) / 38) ** 2) if k % 3 == 1 else 0
        poche = 7 * math.exp(-((y - ym) / 16) ** 2) if k % 3 == 2 else 0
        c = 16 + sortie + e_ * (2.8 * math.sin(y / 23 + ph[0]) + 1.2 * math.sin(y / 8.5 + ph[1]))
        w = 8.2 + poche + e_ * (2.2 * math.sin(y / 17 + ph[2]) + 0.9 * math.sin(y / 6.1 + ph[3])
                                + sum(a * math.exp(-((y - yk) / 6.5) ** 2) for yk, a in gouttes))
        gauche.append((c - w * (1 + 0.12 * e_ * math.sin(y / 3.7 + ph[4])), y))
        droite.append((c + w * (1 + 0.12 * e_ * math.sin(y / 4.3 + ph[5])), y))
        reflet.append((c - w * 0.42, y))
    pts = gauche + droite[::-1]
    d = "M" + " L".join(f"{x:.2f} {y:.2f}" for x, y in pts) + " Z"
    halo = ("M" + " L".join(f"{x - 2.4:.2f} {y:.2f}" for x, y in gauche) + " L"
            + " L".join(f"{x + 2.4:.2f} {y:.2f}" for x, y in droite[::-1]) + " Z")
    r = "M" + " L".join(f"{x:.2f} {y:.2f}" for x, y in reflet if 6 < y < bas - 6)
    a_, b_ = COUL[k % 10], COUL[(k + 1) % 10 or 10]
    gtt = ""
    for i in range(4):
        yy = rnd.uniform(30, bas - 30)
        xx = 16 + rnd.choice([-1, 1]) * rnd.uniform(13, 17)
        rr = rnd.uniform(0.9, 2.1)
        gtt += (f'<circle cx="{xx:.1f}" cy="{yy:.1f}" r="{rr:.1f}" fill="url(#cg{k})"/>'
                f'<circle cx="{xx - rr * .35:.1f}" cy="{yy - rr * .35:.1f}" r="{rr * .3:.1f}" fill="#fff" opacity=".7"/>')
    bout = ""
    if fin:
        bout = (f'<circle cx="16" cy="{bas + 6}" r="13" fill="url(#cg{k})"/>'
                f'<circle cx="12" cy="{bas + 1}" r="3.4" fill="#fff" opacity=".6"/>')
    return (f'<svg class="chemin" viewBox="0 0 420 297"><defs><linearGradient id="cg{k}" x1="0" y1="0" x2="0" y2="297" '
            f'gradientUnits="userSpaceOnUse"><stop offset="0" stop-color="{a_}"/><stop offset="1" stop-color="{b_}"/></linearGradient></defs>'
            f'<path d="{halo}" fill="url(#cg{k})" opacity=".14"/><path d="{d}" fill="url(#cg{k})"/>'
            f'<path d="{r}" fill="none" stroke="#fff" stroke-width=".9" stroke-linecap="round" opacity=".55"/>{gtt}{bout}</svg>')
