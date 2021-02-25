pragma solidity ^0.4.24;

contract Sample {
    event SendFlag(address _addr);

    bool public sendFlag = false;
    uint randomNumber = RN;

    function emitEvent() public {
        emit SendFlag(msg.sender);
    }

    function setVariable() public {
        sendFlag = true;
    }
}