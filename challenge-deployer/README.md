# A Smart Contract Challenge Deployer for CTFs

### How to run

1. Copy the whole `challenge-deployer/` directory to a new directory.
2. Copy your source files (.sol files), `art.txt`, and `flag.txt` to the `app/` directory.
3. Setup environment variables in the `.env` file. `CHAL_FILE` is the source file to be compiled, and `CONT_NAME` is the contract to be deployed. For example, `Sample.sol` and `<stdin>:Sample`.
4. In `Dockerfile`, select the version of solc to be installed.
5. **IMPORTANT** If necessary, modify the `check_solved` function and related logic in `app/server.py`. For example, for challenges `Bank` and `Creativity` from Balsn CTF 2019, players have to provide the hash of a transaction that emits a specific event, indicating that they have solved the challenge.
6. Run `docker-compose up`.
