pragma solidity ^0.5.10;

contract Sample {
    event SendFlag(address _addr);

    uint public value;
    uint randomNumber = RN;

    function callsendflag(uint v) public {
        value = v;
        emit SendFlag(msg.sender);
        selfdestruct(msg.sender);
    }
    function setvalue(uint v) public {
        value = v;
    }
}
