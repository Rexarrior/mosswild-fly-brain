"""Fit only a regularized motor readout; connectome weights remain unchanged."""
import argparse
import json
import random
from pathlib import Path
import numpy as np
from runtime import NativeBrain,decode,decode_learned,neural_features,LAB,ROOT

def main():
    parser=argparse.ArgumentParser();parser.add_argument("--neural-ms",type=int,default=20);parser.add_argument('--rounds',type=int,default=3);args=parser.parse_args()
    assert 10<=args.neural_ms<=100 and 1<=args.rounds<=10
    calibration=json.loads((LAB/'calibration.json').read_text())
    folder=LAB/f'readout-training-{args.neural_ms}ms';folder.mkdir(exist_ok=True)
    models={};report={}
    for backend in ['siliconfly','flybrain']:
        dataset=[]
        with NativeBrain(backend,'readout-training') as brain:
            for seed in [101,202,303]:
                for round_ in range(args.rounds):
                    conditions=[(turn,drive) for turn in [-1,-.6,-.25,0,.25,.6,1] for drive in [0,.08,.28,.6,1]]
                    random.Random(seed+round_*997).shuffle(conditions)
                    for j,(turn,drive) in enumerate(conditions):
                        for tick in range(8):
                            raw=brain.step(id='train',turn=turn,drive=drive,ms=args.neural_ms,seed=seed,reset=(round_==0 and j==0 and tick==0))
                            if tick>=4:dataset.append(dict(seed=seed,round=round_,target=[turn,drive],raw=raw))
                    print(backend,'seed',seed,'round',round_,'samples',len(dataset),flush=True)
        train=[d for d in dataset if d['seed']!=303];test=[d for d in dataset if d['seed']==303]
        x=np.asarray([neural_features(d['raw']) for d in train]);y=np.asarray([d['target'] for d in train])
        reg=np.eye(x.shape[1])*.15;reg[0,0]=.001
        coef=np.linalg.solve(x.T@x+reg,x.T@y)
        xt=np.asarray([neural_features(d['raw']) for d in test]);yt=np.asarray([d['target'] for d in test])
        candidate=dict(enabled=True,turn=coef[:,0].tolist(),drive=coef[:,1].tolist())
        pred=np.asarray([[decode_learned(d['raw'],calibration[backend],candidate)[k] for k in ['turn','drive']] for d in test])
        base=np.asarray([[decode(d['raw'],calibration[backend])[k] for k in ['turn','drive']] for d in test])
        rmse=lambda z:np.sqrt(np.mean((z-yt)**2,axis=0)).tolist()
        old,new=rmse(base),rmse(pred)
        enabled=sum(new)<sum(old)*.98
        models[backend]=dict(enabled=enabled,turn=coef[:,0].tolist(),drive=coef[:,1].tolist(),training_seeds=[101,202],validation_seed=303,neural_ms=args.neural_ms,regularization=.15,features='bias,L,R,F,L2,R2,F2,LR,LF,RF; rates scaled by 400,400,250')
        by_round={}
        for round_ in range(args.rounds):
            indexes=[i for i,d in enumerate(test) if d['round']==round_]
            by_round[round_]=dict(baseline_rmse=np.sqrt(np.mean((base[indexes]-yt[indexes])**2,axis=0)).tolist(),learned_rmse=np.sqrt(np.mean((pred[indexes]-yt[indexes])**2,axis=0)).tolist())
        late=by_round[args.rounds-1]
        enabled=enabled and sum(late['learned_rmse'])<=sum(late['baseline_rmse'])*1.02
        models[backend]['enabled']=enabled
        report[backend]=dict(samples=len(dataset),baseline_rmse=old,learned_rmse=new,enabled=enabled,neural_ms=args.neural_ms,rounds=args.rounds,neural_seconds_per_seed=args.rounds*35*8*args.neural_ms/1000,by_round=by_round)
        (folder/(backend+'.json')).write_text(json.dumps(dataset))
        print(backend,json.dumps(report[backend]),flush=True)
    (ROOT/'Config/BrainReadout.json').write_text(json.dumps(models,indent=2)+'\n')
    (folder/'validation.json').write_text(json.dumps(report,indent=2)+'\n')

if __name__=='__main__':main()
