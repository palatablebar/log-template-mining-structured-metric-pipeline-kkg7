import type { SlotType } from '../types/models';

/** 槽位配色：全部落在浅灰蓝/深青灰/琥珀体系里，靠明度与饱和度区分。 */
export const slotClass = (slot: SlotType | string): string => {
  switch (slot) {
    case 'num':
      return 'slot slot-num';
    case 'ip':
    case 'uuid':
    case 'hex':
      return 'slot slot-code';
    case 'path':
      return 'slot slot-path';
    case 'ts':
      return 'slot slot-ts';
    case 'str':
      return 'slot slot-str';
    case 'unknown':
      return 'slot slot-unknown';
    default:
      return 'slot slot-static';
  }
};
