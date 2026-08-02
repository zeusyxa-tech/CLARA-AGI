# USER PROJECT BACKUP INDEX

Generated: 2026-08-02
Purpose: Single-file truth for user + future AI assistants. Contains every active project,
its location, GitHub URL, current state, conventions, and critical addresses.
All addresses/tx hashes are full, no truncation.

---

## REPOSITORY INVENTORY

| Local Path | GitHub URL | Branch/Status | Notes |
|---|---|---|---|
| /home/acer/ACE-Step-1.5 | https://github.com/ACE-Step/ACE-Step-1.5 | main (up-to-date) | External repo |
| /home/acer/Documents/kokoro | https://github.com/quanta-tect/quanta | main (synced) | Contains litellm subdirectory |
| /home/acer/Documents/kokoro/litellm | https://github.com/BerriAI/litellm | main (submodule-like) | External repo embedded |
| /home/acer/Downloads/develop-a-polished-browser-game | https://github.com/quanta-tect/gravity-dash | main (up-to-date) | Browser game |
| /home/acer/Downloads/EA31337-Libre | https://github.com/EA31337/EA31337-Libre | main (up-to-date) | External repo |
| /home/acer/Downloads/geo-viet | https://github.com/quanta-tect/geo-viet | main (up-to-date) | GEO static site |
| /home/acer/Downloads/geo-viet-phase5 | https://github.com/quanta-tect/geo-viet | main (up-to-date) | GEO static site variant |
| /home/acer/Downloads/geo-viet-repo | https://github.com/quanta-tect/geo-viet | main (up-to-date) | GEO static site variant |
| /home/acer/Downloads/geo-viet-work | https://github.com/quanta-tect/geo-viet | main (up-to-date) | GEO static site variant |
| /home/acer/Downloads/quanta-protocol | https://github.com/quanta-tect/quanta-protocol | main (up-to-date) | Protocol contracts |
| /home/acer/Downloads/SafeAgentKit | https://github.com/quanta-tect/SafeAgentKit | main (up-to-date) | Safe agent SDK |
| /home/acer/ecc-tools | https://github.com/affaan-m/ECC | main (403 on push) | Permission issue |
| /home/acer/.hermes/hermes-agent | https://github.com/NousResearch/hermes-agent | main (external) | Hermes core |
| /home/acer/open-toolbox | https://github.com/quanta-tect/open-toolbox | main (up-to-date) | Toolbox app |
| /home/acer/open-toolbox-backup | https://github.com/quanta-tect/open-toolbox | main (synced) | Toolbox backup |
| /home/acer/polkadot-sdk-minimal-template | https://github.com/paritytech/polkadot-sdk-minimal-template | main (up-to-date) | Polkadot template |
| /home/acer/projects/ai-remixmate | https://github.com/Chunduri-Aditya/ai-remixmate | main (up-to-date) | External DJ engine |
| /home/acer/projects/quanta | https://github.com/zeusyxa-tech/Zeusxya | feat/rebrand-quanta-to-zeusyxa-v2 (synced) | REBRAND: Quanta -> Zeusyxa |
| /home/acer/quanta-github | https://github.com/quanta-tect/quanta | feature/agentpay-demo (conflict) | Demo dashboard on feature branch |
| /home/acer/quanta-github-backup | https://github.com/quanta-tect/quanta | backup/20260802 (synced) | Backup of agentpay demo |
| /home/acer/Zeusxya | https://github.com/zeusyxa-tech/Zeusxya | main (up-to-date) | Main Zeusyxa repo |

---

## BACKUP BRANCHES (created 2026-02 backup)

| Repo | Backup Branch | Contents |
|---|---|---|
| quanta-tect/quanta | backup/20260802 | agentpay-dashboard demo + README updates |
| quanta-tect/quanta | backup/feature/agentpay-demo-202608 | agentpay-dashboard demo (from quanta-github) |
| zeusyxa-tech/Zeusxya | feat/rebrand-quanta-to-zeusyxa-v2 | Full rebrand: Quanta -> Zeusyxa |
| zeusyxa-tech/open-toolbox | main | Moved from quanta-tect |

---

## CRITICAL ADDRESSES

### User Wallet (Base Sepolia)
Deployer wallet: 0x2060378AF1916eCFB1A6734405d4f4a62f1560FC

### QUANTA v1.2 Final (Base Sepolia)
QuantaToken: 0x312137fb6943F8f89F5eF0f221aA102035a16625
AIAgentRegistry: 0x10aE5f83F1CF20331186Ea1aD089D8fd3EbA5EEB
AIPaymentChannel: 0xF146e95b97fce1d1800F5F922AE99155711A4314
AIModelMarketplace: 0xFf584b30b2D00Bf0aB694683F06dC7E701fdfd49
Treasury/Deployer: 0x2060378AF1916eCFB1A6734405d4f4a62f1560FC
Multisig (SimpleMultisig 1-of-1): 0x9261020D451a631AcB26e5BcA26b7BD3c95b726D

### ZEUSYXA v1.2 Final (Base Sepolia) - REBRAND
ZeusyxaTokenV2: 0x6d089d25035868358952b4d3644f8dAdcCc3295a
ZeusyxaVestingWallet: 0xDc1B7aB0e7aE57bbB66ead2d9998bDA9127A291D
ZeusyxaTreasuryController: 0xb8D10Ba1839597c0c76a60455E231Ac2bA837901
ZeusyxaRewardsDistributor: 0x3bED931A6A4F0246d152c2532BB9015850657446
AIAgentRegistry (v1.2): 0x10aE5f83F1CF20331186Ea1aD089D8fd3EbA5EEB
AIPaymentChannel (v1.2): 0xF146e95b97fce1d1800F5F922AE99155711A4314
AIModelMarketplace (v1.2): 0xFf584b30b2D00Bf0aB694683F06dC7E701fdfd49
Treasury Multisig: 0x1d6a9512fF4A98C192A99Adea934ac3f83035953
Team Multisig: 0x1d6a9512fF4A98C192A99Adea934ac3f83035953

---

## PROJECT CONVENTIONS (from AGENTS.md files)

### Zeusyxa / Quanta Protocol
- Solidity 0.8.24, OpenZeppelin, Foundry
- TypeScript SDK, viem, Node.js (ESM)
- Base Sepolia testnet (chainId 84532)
- NEVER hardcode private keys
- ALWAYS run forge test after contract changes
- SDK uses viem (not ethers.js). Payment channel needs prior approve()
- User speaks Vietnamese, prefers sed over new files

### AI RemixMate
- Python + React DJ engine
- FastAPI backend with async job queue + SQLite
- React frontend (Vite + TypeScript) with 8 pages
- Demucs stem separation, beat-grid lock, mastering to -14 LUFS
- Tests: pytest, librosa-dependent tests auto-skipped if unavailable
- Ports: API 8000, Frontend 5173

### Hermes Agent (.hermes/hermes-agent)
- Core prompt caching is sacred (do not mutate past context mid-conversation)
- Narrow waist, capability at edges
- Plugins/skills over core growth
- Never add new HERMES_* env vars for non-secret config
- Behavior contracts over snapshots in tests

### ECC Tools (ecc-tools)
- Production-ready AI coding plugin
- 67 agents, 271 skills, 92 commands
- Agent-first, test-driven, security-first
- Commit format: `<type>: <description>`
- Minimum 80% test coverage

---

## DEPLOYMENT URLS

### Zeusyxa / Quanta
- Landing: open landing/index.html
- Explorer: open explorer/index.html
- Wallet UI: open wallet-ui/index.html
- SDK Demo: cd sdk && npm install && npm run demo:agent
- AgentPay Dashboard: cd demo/agentpay-dashboard && npm install && npm run dev

### AI RemixMate
- React UI: http://localhost:5173
- API docs: http://localhost:8000/docs
- SSE stream: http://localhost:8000/events/stream
- Start: ./start.sh (or ./start.sh api for API only)

### CLARA AGI
- Repo: https://github.com/zeusyxa-tech/CLARA-AGI (private)
- Local: /home/acer/Downloads/CLARA_AGI
- Run: cd /home/acer/Downloads/CLARA_AGI && python3 run_autopilot_bg.py
- Log: data/autopilot_ollama_latest.log
- Memory: 976 episodes, 126 facts, 56 procedures
- Self-improvement + web curriculum + autonomous learning all enabled

---

## REBRAND STATUS

**Active rebrand: Quanta -> Zeusyxa**
- New organization: zeusyxa-tech
- Token symbol: ZYX (was QTA)
- Contracts renamed: QuantaToken -> ZeusyxaToken, etc.
- In progress on branch: feat/rebrand-quanta-to-zeusyxa-v2
- Repos migrated: Zeusxya, open-toolbox
- Still using old names in: quanta-tect org repos (quanta, geo-viet, etc.)

**Important:** When working on Zeusyxa-branded repos, use Zeusyxa names and addresses.
When working on quanta-tect repos, use Quanta names and addresses.

---

## IMPORTANT RULES

1. ALWAYS unset ETHERSCAN_API_KEY + BASESCAN_API_KEY before verify with sourcify
2. DO NOT add [etherscan] section back to foundry.toml
3. NEVER hardcode private keys
4. ALWAYS update DEPLOYMENTS.md + PROJECT_CONTEXT.md after any address change
5. README mixed-content rewrite rule: if README has both old/new addresses, rewrite entire file
6. App.tsx duplicate-keyword rule: scan for duplicate definitions before editing
7. Release prep: rewrite README/CHANGELOG/RELEASE_NOTES, run checks, create clean PR, then release
8. PR hygiene: recreate clean PR from origin/main when GitHub UI flags Unicode/stale state

---

## USER PREFERENCES

- Language: Vietnamese (tiếng Việt)
- Style: concise, direct, action-first
- Income streams: prefers immediate work/payment over apply-wait model
- Outreach: direct tweet/social media over platform freelancing
- Publishes in English for global reach
- Willing to do Fiverr but frustrated by slow onboarding
- Does NOT like apply -> interview -> wait model

---

## ENVIRONMENT

- Host: Linux (7.0.0-28-generic)
- Home: /home/acer
- Auto-start CLARA: `start_clara` + `clara_status` in ~/.bashrc
- `hd` alias: `start_clara; hermes`
- Hermes profile: default
- CLI auth: gh (quanta-tect), token scopes: gist, read:org, repo, workflow
- Web search blocked: Tavily 401, GitHub MCP bad credentials
- Fallback: raw.githubusercontent.com for file access

---

## TODO / PENDING OUTREACH

See: ~/quanta_investor_templates.md
- Tweet @Quanta_Protocol
- Base/Gitcoin grant submissions
- Upwork/Fiverr proposals in progress

---

## BACKUPS DONE (2026-08-02 house move)

All Git repos pushed to GitHub. Key issues:
- Documents/kokoro: resolved rebrand merge conflict, pushed clean
- open-toolbox-backup: rebased and pushed
- quanta-github: created backup branch backup/20260802
- quanta-github-backup: created backup branch backup/20260802
- CLARA-AGI: new private repo created and pushed
- ecc-tools: blocked by 403 (permission denied on affaan-m/ECC)

---

END OF INDEX
