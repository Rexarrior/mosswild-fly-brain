#include "RPGGameMode.h"
#include "RPGCharacter.h"
#include "RPGHUD.h"
ARPGGameMode::ARPGGameMode()
{
    DefaultPawnClass = ARPGCharacter::StaticClass();
    HUDClass = ARPGHUD::StaticClass();
}
