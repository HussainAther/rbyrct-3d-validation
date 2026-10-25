"""Regenerate manuscript Figures 1-5 from paired_cases.csv (Study 1 = 04P, Study 2 = 04Q-B).

Usage (from the repository root):  python make_figures.py . figures
"""
import sys, pandas as pd, numpy as np, matplotlib
matplotlib.use('Agg'); import matplotlib.pyplot as plt
import os
plt.rcParams["pdf.fonttype"] = 42
R = sys.argv[1] if len(sys.argv) > 1 else "."
OUT = sys.argv[2] if len(sys.argv) > 2 else "figures"
os.makedirs(OUT, exist_ok=True)
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':8,'axes.spines.top':False,'axes.spines.right':False,
                     'axes.titlesize':8.5,'axes.labelsize':8,'legend.fontsize':7,'xtick.labelsize':7.5,'ytick.labelsize':7.5})
S = {'Study 1 (Siddon-like)':'experiment04p_full','Study 2 (trilinear)':'experiment04qb_full'}
D = {k: pd.read_csv(f'{R}/results/{v}/paired_cases.csv') for k,v in S.items()}
REP, SUB = '#0072B2', '#D55E00'          # Okabe-Ito blue / vermillion
FAM = ['branches','layers','pores','defects']

# ---- Figure 3: mean paired gain by budget and representation, family means as dots
fig, axes = plt.subplots(1,2,figsize=(7.0,2.8),sharey=True,dpi=300)
for ax,(title,df) in zip(axes,D.items()):
    a = df[df.policy=='adaptive_feedback']
    for j,(ot,col) in enumerate([('replicated',REP),('subvoxel',SUB)]):
        for i,b in enumerate([1024,2048]):
            s = a[(a.object_type==ot)&(a.budget==b)]
            x = i + (j-0.5)*0.36
            ax.bar(x, 100*s.relative_gain.mean(), 0.34, color=col, label=ot if i==0 else None, zorder=2)
            fm = 100*s.groupby('phantom').relative_gain.mean()
            ax.scatter(np.full(len(fm),x)+np.linspace(-0.06,0.06,len(fm)), fm, s=9, color='#222222', zorder=3, linewidths=0)
    ax.axhline(0,color='#555555',lw=0.8,zorder=1); ax.grid(axis='y',color='#E3E3E3',lw=0.6,zorder=0)
    ax.set_xticks([0,1]); ax.set_xticklabels(['1,024 rays','2,048 rays']); ax.set_title(title)
axes[0].set_ylabel('Paired RMSE gain vs feedback-off (%)')
axes[0].legend(frameon=False,loc='lower left')
fig.tight_layout(); fig.savefig(f'{OUT}/figure3.png',facecolor='white',dpi=600); fig.savefig(f'{OUT}/figure3.pdf',facecolor='white'); plt.close(fig)

# ---- Figure 4: family x representation x offset at 2,048 rays
combos = [('replicated',0.0,REP,None),('replicated',0.15,REP,'////'),('subvoxel',0.0,SUB,None),('subvoxel',0.15,SUB,'////')]
fig, axes = plt.subplots(1,2,figsize=(7.0,2.9),sharey=True,dpi=300)
for ax,(title,df) in zip(axes,D.items()):
    a = df[(df.policy=='adaptive_feedback')&(df.budget==2048)]
    for k,(ot,off,col,h) in enumerate(combos):
        vals=[100*a[(a.phantom==f)&(a.object_type==ot)&(a.offset==off)].relative_gain.mean() for f in FAM]
        ax.bar(np.arange(4)+(k-1.5)*0.2, vals, 0.19, color=col if h is None else 'white', edgecolor=col, hatch=h, lw=0.8,
               label=f'{ot}, offset {off:g}', zorder=2)
    ax.axhline(0,color='#555555',lw=0.8,zorder=1); ax.grid(axis='y',color='#E3E3E3',lw=0.6,zorder=0)
    ax.set_xticks(range(4)); ax.set_xticklabels([f.capitalize() for f in FAM]); ax.set_title(title)
axes[0].set_ylabel('Mean paired gain vs feedback-off (%)')
axes[1].legend(frameon=False,loc='lower left',ncol=1)
fig.tight_layout(); fig.savefig(f'{OUT}/figure4.png',facecolor='white',dpi=600); fig.savefig(f'{OUT}/figure4.pdf',facecolor='white'); plt.close(fig)

# ---- Figure 5: gate vs ungated feedback, Study 2 subvoxel, 2,048 rays
df = D['Study 2 (trilinear)']; a = df[(df.object_type=='subvoxel')&(df.budget==2048)]
fig, ax = plt.subplots(figsize=(5.2,2.8),dpi=300)
for k,(pol,lab,col,h) in enumerate([('adaptive_feedback','Full feedback','#0072B2',None),('reliability_gate','Reliability gate','#E69F00',None)]):
    vals=[100*a[(a.phantom==f)&(a.policy==pol)].relative_gain.mean() for f in FAM]
    ax.bar(np.arange(4)+(k-0.5)*0.36, vals, 0.34, color=col, label=lab, zorder=2)
ax.axhline(0,color='#555555',lw=0.8); ax.grid(axis='y',color='#E3E3E3',lw=0.6,zorder=0)
ax.set_xticks(range(4)); ax.set_xticklabels([f.capitalize() for f in FAM])
ax.set_ylabel('Gain vs feedback-off (%)'); ax.legend(frameon=False,loc='lower left')
fig.tight_layout(); fig.savefig(f'{OUT}/figure5.png',facecolor='white',dpi=600); fig.savefig(f'{OUT}/figure5.pdf',facecolor='white'); plt.close(fig)
print('ok')

# Figure 1 is a vector schematic, generated from the declared acquisition sequence.
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
plt.rcParams['pdf.fonttype'] = 42
plt.rcParams['ps.fonttype'] = 42
fig, ax = plt.subplots(figsize=(7.0, 3.0), dpi=600)
ax.set(xlim=(0,10), ylim=(0,4)); ax.axis('off')
boxes = [(0.3,2.4,'Warm start\n128 geometry-selected rays'),
         (3.5,2.4,'Provisional reconstruction\nAcquired measurements only'),
         (6.7,2.4,'Score candidate rays\nFeatures and coverage'),
         (6.7,.6,'Acquire next batch\nCommit selected observations'),
         (0.3,.6,'Final reconstruction\nAt the prescribed ray budget')]
for x,y,label in boxes:
    ax.add_patch(FancyBboxPatch((x,y),2.9,1.05,boxstyle='round,pad=0.04',facecolor='#F3F5F7',edgecolor='#243746',lw=1))
    ax.text(x+1.45,y+.525,label,ha='center',va='center',fontsize=8.3)
for start,end in [((3.25,2.93),(3.43,2.93)),((6.45,2.93),(6.63,2.93)),((8.15,2.35),(8.15,1.72)),((6.65,1.12),(3.25,1.12))]:
    ax.add_patch(FancyArrowPatch(start,end,arrowstyle='-|>',mutation_scale=12,color='#243746',lw=1.2))
ax.annotate('',xy=(4.95,2.35),xytext=(6.7,1.65),arrowprops=dict(arrowstyle='-|>',connectionstyle='angle,angleA=180,angleB=-90,rad=10',color='#0072B2',lw=1.2))
ax.text(4.7,2.0,'Continue below budget',ha='right',fontsize=8,color='#0072B2')
ax.text(4.9,.85,'Budget reached',ha='center',fontsize=8)
fig.tight_layout(pad=.6)
fig.savefig(f'{OUT}/figure1.png',facecolor='white',dpi=600)
fig.savefig(f'{OUT}/figure1.pdf',facecolor='white')
plt.close(fig)

# Figure 2 uses native arrays from the original phantom-generation functions.
from experiment_04p import phantoms
coarse, fine = phantoms(16), phantoms(32)
fig, axes = plt.subplots(4,3,figsize=(7.5,8.2),dpi=600)
for row,family in enumerate(FAM):
    replicated = np.repeat(np.repeat(np.repeat(coarse[family],2,axis=0),2,axis=1),2,axis=2)
    for col,vol in enumerate([coarse[family],replicated,fine[family]]):
        ax=axes[row,col]
        ax.imshow(vol[vol.shape[0]//2],cmap='gray',vmin=0,vmax=1,interpolation='nearest')
        ax.set_xticks([]);ax.set_yticks([])
        if row==0:ax.set_title(['Coarse 16³','Replicated 32³','Analytic 32³'][col],fontsize=10)
        if col==0:ax.set_ylabel(family.capitalize(),fontsize=10)
fig.tight_layout(pad=.7,w_pad=.6,h_pad=.5)
fig.savefig(f'{OUT}/figure2.png',facecolor='white',dpi=600)
fig.savefig(f'{OUT}/figure2.pdf',facecolor='white',dpi=600)
plt.close(fig)
