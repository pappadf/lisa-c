/* Menu Manager (Menus unit, SYS1LIB) for C. */
#ifndef LISA_MENUS_H
#define LISA_MENUS_H

#include "lisa/quickdraw.h"

enum { maxItem = 31, noMark = 0, checkMark = 142, appleMark = 143 };

typedef struct {
    Integer menuId;
    Integer menuWidth;
    Integer menuHeight;
    void *drawProc;
    void *chooseProc;
    unsigned char enableFlags[4];       /* packed boolean[0..31]: see MenuEnabled */
    void *menuData;
} MenuInfo;

/* enableFlags is a Pascal packed array of boolean: item i (0 = the whole
 * menu) is bit i % 8 of byte i / 8.  EnableItem/DisableItem change it. */
#define MenuEnabled(m, i) (((m)->enableFlags[(i) >> 3] >> ((i) & 7)) & 1)

pascal void MenuSelect(Point startPt, Integer *whichMenu, Integer *whichItem) LISA_IU(MENUSELE);
pascal void DrawMenuBar(void) LISA_IU(DRAWMENU);
pascal void ClearMenuBar(void) LISA_IU(CLEARMEN);
pascal void HiLiteMenu(Integer menuId) LISA_IU(HILITEME);
pascal void InsertMenu(MenuInfo *menu, Integer beforeId) LISA_IU(INSERTME);
pascal void DeleteMenu(Integer menuId) LISA_IU(DELETEME);
pascal void EnableItem(MenuInfo *menu, Integer item) LISA_IU(ENABLEIT);
pascal void DisableItem(MenuInfo *menu, Integer item) LISA_IU(DISABLEI);
pascal void CheckItem(MenuInfo *menu, Integer item, Boolean checked) LISA_IU(CHECKITE);
pascal void GetItem(MenuInfo *menu, Integer item, unsigned char *itemString) LISA_IU(GETITEM);
pascal void SetItem(MenuInfo *menu, Integer item, const unsigned char *itemString) LISA_IU(SETITEM);

#endif
