import json
from pathlib import Path
import tempfile
import unittest
import numpy as np
import pandas as pd
from figure_03_08m_primary import load_verified_data, draw_figure

class Figure3Tests(unittest.TestCase):
    def test_synthetic_complete_archive(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); m = root/'m'; q = root/'q'; o = root/'fig'; m.mkdir(); q.mkdir(); o.mkdir()
            ids = [f'obj_{j}' for j in range(100,108)]
            g = np.array([.04,.043,.046,.049,.051,.055,.06,.062])
            d = np.array([.02,.04,.06,.07,.08,.09,.1,.11])
            obj = pd.DataFrame({'size':[32]*8,'object_id':ids,'acquired':[2048]*8,'policy':['information_diag']*8,'n_conditions':[4]*8,'mean_global_gain':g,'mean_defect_gain':d})
            obj.to_csv(m/'object_level_summary.csv',index=False)
            agg = pd.DataFrame([{'acquired':2048,'policy':'information_diag','mean_global_gain':g.mean(),'mean_defect_gain':d.mean(),'object_global_wins':8,'object_defect_wins':8}]); agg.to_csv(m/'aggregate_summary.csv',index=False)
            (m/'primary_endpoint.json').write_text(json.dumps({'primary':{'acquired':2048,'policy':'information_diag','n_objects':8,'mean_global_gain':g.mean(),'mean_defect_gain':d.mean(),'object_global_wins':8,'object_defect_wins':8}}))
            obj[['object_id','acquired','n_conditions','mean_global_gain','mean_defect_gain']].to_csv(q/'object_level_replayed.csv',index=False)
            agg.drop(columns='policy').to_csv(q/'aggregate_replayed.csv',index=False)
            values,primary,provenance=load_verified_data(m,q)
            self.assertEqual(len(values),8)
            self.assertEqual(provenance['global_object_wins'],8)
            draw_figure(values,o,100*g.mean(),100*d.mean())
            self.assertEqual(len(list(o.iterdir())),3)
            obj.loc[0,'mean_global_gain'] += .01
            obj.to_csv(m/'object_level_summary.csv',index=False)
            with self.assertRaisesRegex(ValueError,'08M vs 08Q'):
                load_verified_data(m,q)

if __name__=='__main__':
    unittest.main()
