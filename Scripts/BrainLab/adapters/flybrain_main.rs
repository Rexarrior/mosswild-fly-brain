#![allow(dead_code)]
mod metal_engine;
mod npy;
mod pack;
mod parameters;
mod stimulus;
use anyhow::Result;
use std::{collections::HashMap, io::{self, BufRead, Write}, time::Instant};
use serde::Deserialize;
use serde_json::json;
use metal_engine::MetalEngine;
use pack::ConnectomePack;
use parameters::ModelParameters;
use stimulus::EventSchedule;

#[derive(Deserialize)]
struct Groups { inputs: HashMap<String, Vec<u32>>, outputs: HashMap<String, Vec<u32>> }
#[derive(Deserialize)]
struct Request { id: String, turn: f64, drive: f64, threat: f64, ms: usize, seed: u64, ablate: bool, reset: bool, release: bool, #[serde(default)] channels: Option<Vec<f64>> }
struct Brain { engine: MetalEngine, tick: u64 }
fn hash(mut v: u64) -> u64 {
    v = v.wrapping_add(0x9e3779b97f4a7c15);
    v = (v ^ (v >> 30)).wrapping_mul(0xbf58476d1ce4e5b9);
    v = (v ^ (v >> 27)).wrapping_mul(0x94d049bb133111eb);
    v ^ (v >> 31)
}
fn main() -> Result<()> {
    let args: Vec<String> = std::env::args().collect();
    let pack = ConnectomePack::open(&args[1])?;
    let data: serde_json::Value = serde_json::from_str(&std::fs::read_to_string(&args[2])?)?;
    let groups: Groups = serde_json::from_value(data["flybrain"].clone())?;
    let names = ["left", "right", "forward", "escape"];
    let targets: Vec<u32> = names.iter().flat_map(|k| groups.inputs[*k].clone()).collect();
    let probes: Vec<u32> = names.iter().flat_map(|k| groups.outputs[*k].clone()).collect();
    let mut brains: HashMap<String, Brain> = HashMap::new();
    for line in io::stdin().lock().lines() {
        let result = (|| -> Result<serde_json::Value> {
            let r: Request = serde_json::from_str(&line?)?;
            if r.release { brains.remove(&r.id); return Ok(json!({"released":true})); }
            if r.reset { brains.remove(&r.id); }
            if !brains.contains_key(&r.id) {
                anyhow::ensure!(brains.len() < 32, "brain capacity exceeded");
                let silent: Vec<u32> = if r.ablate { (0..pack.neuron_count() as u32).collect() } else { vec![] };
                let engine = MetalEngine::new(&pack, ModelParameters::default(), None, None, &targets, &silent)?;
                brains.insert(r.id.clone(), Brain { engine, tick: 0 });
            }
            let brain = brains.get_mut(&r.id).unwrap();
            let ms = r.ms.clamp(1, 200);
            let steps = ms * 10;
            let levels = [r.turn.max(0.0), (-r.turn).max(0.0), r.drive, r.threat];
            let probabilities: Vec<f64> = if let Some(ref c) = r.channels {
                anyhow::ensure!(c.len() == 8 && c.iter().all(|v| v.is_finite() && *v >= 0.0 && *v <= 1.0), "eight sensory channels in [0,1] required");
                names.iter().enumerate().flat_map(|(side,k)| {
                    groups.inputs[*k].iter().enumerate().map(move |(rank,_)| {
                        if side < 2 { c[(rank % 3)*2+side]*0.045 }
                        else { c[side+4]*0.015 }
                    })
                }).collect()
            } else {
                names.iter().enumerate().flat_map(|(i,k)| vec![levels[i].clamp(0.0,1.0)*0.015; groups.inputs[*k].len()]).collect()
            };
            let start = Instant::now();
            let mut counts = Vec::with_capacity(steps * targets.len());
            for tick in 0..steps {
                for (lane, p) in probabilities.iter().enumerate() {
                    let key = r.seed ^ (brain.tick + tick as u64).wrapping_mul(0x9e3779b97f4a7c15) ^ (lane as u64).wrapping_mul(0xbf58476d1ce4e5b9);
                    let uniform = (hash(key) >> 11) as f64 / ((1_u64 << 53) as f64);
                    counts.push(u8::from(uniform < *p));
                }
            }
            let schedule = EventSchedule::new(targets.clone(), counts, steps, pack.neuron_count())?;
            let window = brain.engine.run_window(&schedule, &probes)?;
            brain.tick += steps as u64;
            let mut out = json!({"id":r.id, "neurons":pack.neuron_count(), "edges":pack.edge_count(), "neural_ms":ms, "wall_ms":start.elapsed().as_secs_f64()*1000.0, "allocated_bytes":brain.engine.allocated_bytes(), "device":brain.engine.device_name()});
            let mut offset = 0;
            for name in names {
                let n = groups.outputs[name].len();
                let count: u32 = window.spike_count_deltas[offset..offset+n].iter().sum();
                out[name] = json!(if name == "escape" { f64::from(count > 0) } else { count as f64 * 1000.0 / (ms * n) as f64 });
                offset += n;
            }
            Ok(out)
        })();
        let out = match result { Ok(v) => v, Err(e) => json!({"error":format!("{e:#}")}) };
        println!("{out}"); io::stdout().flush()?;
    }
    Ok(())
}
