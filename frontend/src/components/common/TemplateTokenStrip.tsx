import { SLOT_LABELS } from '../../constants/enums';
import { slotClass } from '../../utils/slotColor';
import type { SlotType } from '../../types/models';

interface TemplateTokenStripProps {
  templateStr: string;
  slotTypes?: SlotType[] | string[];
  slotNames?: string[];
  highlight?: boolean;
}

/**
 * 业务共享组件：模板串按 token 渲染，通配位按槽位类型着色。
 * /templates 列表与 /import 挖掘预览共用。
 */
export const TemplateTokenStrip = ({ templateStr, slotTypes = [], slotNames = [], highlight }: TemplateTokenStripProps) => {
  const tokens = templateStr.split(' ');
  return (
    <div className="token-strip">
      {tokens.map((token, index) => {
        const slot = (slotTypes[index] ?? 'static') as SlotType | 'static';
        const name = slotNames[index];
        const isSlot = token === '<*>' || (slot !== 'static' && slot !== undefined);
        return (
          <span
            key={`${index}-${token}`}
            className={isSlot ? slotClass(slot) : 'token'}
            title={name ? `${name} · ${SLOT_LABELS[slot as SlotType] ?? slot}` : SLOT_LABELS[slot as SlotType] ?? ''}
            style={highlight && isSlot ? { outline: '1px dashed var(--amber-deep)' } : undefined}
          >
            {token}
          </span>
        );
      })}
    </div>
  );
};
