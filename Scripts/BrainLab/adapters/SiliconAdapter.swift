import Foundation

struct Groups: Decodable { let inputs: [String: [Int]]; let outputs: [String: [Int]] }
struct Request: Decodable {
    var id: String = "probe"
    var turn: Float = 0
    var drive: Float = 0
    var threat: Float = 0
    var ms: Int = 100
    var seed: UInt32 = 1
    var ablate: Bool = false
    var reset: Bool = false
    var release: Bool = false
    // Food L/R, water L/R, home L/R, arousal, threat. No winner is computed.
    var channels: [Float]? = nil
}

@main struct Adapter {
    static func main() throws {
        let groupsPath = CommandLine.arguments[1]
        let all = try JSONSerialization.jsonObject(with: Data(contentsOf: URL(fileURLWithPath: groupsPath))) as! [String: Any]
        let groups = try JSONDecoder().decode(Groups.self, from: JSONSerialization.data(withJSONObject: all["siliconfly"]!))
        guard let connectome = loadConnectome() else { exit(2) }
        var brains: [String: MetalSim] = [:]
        while let line = readLine() {
            do {
                let r = try JSONDecoder().decode(Request.self, from: Data(line.utf8))
                if r.release {
                    brains.removeValue(forKey: r.id)
                    print("{\"released\":true}"); fflush(stdout); continue
                }
                if r.reset { brains.removeValue(forKey: r.id) }
                if brains[r.id] == nil {
                    guard brains.count < 32 else { throw NSError(domain: "capacity", code: 1) }
                    var params = SimParams()
                    if r.ablate { params.weightScale = 0 }
                    guard let sim = MetalSim(connectome: connectome, spikeBus: nil, seed: r.seed, params: params) else { exit(3) }
                    brains[r.id] = sim
                }
                let sim = brains[r.id]!
                let ms = min(200, max(1, r.ms))
                let start = DispatchTime.now().uptimeNanoseconds
                if let channels = r.channels {
                    guard channels.count == 8 && channels.allSatisfy({ $0.isFinite && $0 >= 0 && $0 <= 1 }) else {
                        throw NSError(domain: "eight sensory channels in [0,1] required", code: 2)
                    }
                    // Interleave ranked partners so each modality has strong and weak partners.
                    // Six lateral groups + forward + escape fit the upstream eight-stimulus queue.
                    for modality in 0..<3 {
                        for (side, name) in ["left", "right"].enumerated() {
                            let cells = groups.inputs[name]!.enumerated().filter { $0.offset % 3 == modality }.map { $0.element }
                            sim.stimulate(cells, strength: channels[modality * 2 + side] * 0.66, durationMs: ms + 1)
                        }
                    }
                    sim.stimulate(groups.inputs["forward"]!, strength: channels[6] * 0.22, durationMs: ms + 1)
                    sim.stimulate(groups.inputs["escape"]!, strength: channels[7] * 0.22, durationMs: ms + 1)
                } else {
                    let inputs: [String: Float] = ["left": max(0, r.turn), "right": max(0, -r.turn), "forward": max(0, min(1, r.drive)), "escape": max(0, min(1, r.threat))]
                    for (name, level) in inputs where level > 0 {
                        sim.stimulate(groups.inputs[name]!, strength: level * 0.22, durationMs: ms + 1)
                    }
                }
                sim.step(ms)
                let out: [String: Any] = ["id": r.id, "left": sim.rateDNaL, "right": sim.rateDNaR, "forward": sim.rateFwd, "escape": sim.consumeGF() ? 1 : 0, "population": sim.ratePop, "spikes": sim.totalSpikes, "wall_ms": Double(DispatchTime.now().uptimeNanoseconds - start) / 1e6, "neural_ms": ms, "neurons": connectome.n, "edges": connectome.e]
                print(String(data: try JSONSerialization.data(withJSONObject: out, options: [.sortedKeys]), encoding: .utf8)!)
                fflush(stdout)
            } catch {
                let out = ["error": String(describing: error)]
                print(String(data: try JSONSerialization.data(withJSONObject: out), encoding: .utf8)!)
                fflush(stdout)
            }
        }
    }
}
