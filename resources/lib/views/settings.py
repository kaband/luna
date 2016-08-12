import os

import xbmcaddon
import xbmcgui
from resources.lib.di.requiredfeature import RequiredFeature
from resources.lib.model.kodi_gui_workarounds.linkedlistitem import LinkedListItem
from resources.lib.model.kodi_gui_workarounds.settinggroup import SettingGroup
from resources.lib.model.kodi_gui_workarounds.rotaryselect import RotarySelect
from resources.lib.model.kodi_gui_workarounds.slider import Slider


class Settings(xbmcgui.WindowXMLDialog):
    def __new__(cls, *args, **kwargs):
        return super(Settings, cls).__new__(cls, 'settings.xml', xbmcaddon.Addon().getAddonInfo('path'))

    def __init__(self, controller):
        super(Settings, self).__init__('settings.xml', xbmcaddon.Addon().getAddonInfo('path'))
        self.controller = controller
        self.settings_parser = RequiredFeature('settings-parser').request()
        self.ok_btn = None
        self.cancel_btn = None
        self.settings = []
        self.category_list = None
        self.settings_workarounds = {}
        self.button_dict = {}
        self.forward_controls = []
        self.needs_state_update = {}
        self.setting_id_group = {}
        self.selected_cat_cache = ''
        self.logger = RequiredFeature('logger').request()

    def onInit(self):
        self.settings = [setting for key, setting in self.settings_parser.get_settings().iteritems()]
        self.settings.sort(key=lambda x: x.priority, reverse=False)
        self.category_list = self.getControl(302)
        self.ok_btn = self.getControl(303)
        self.cancel_btn = self.getControl(304)
        self.build_list()
        self.setFocusId(302)

    def build_list(self):
        categories = []

        for category in self.settings:
            item = xbmcgui.ListItem()
            item.setLabel(category.cat_label)
            item.setProperty('id', str(category.priority))
            categories.append(item)

        self.logger.info("Adding category list items")
        self.category_list.addItems(categories)

        for category in self.settings:
            self.build_settings_list(category, category.settings)

        for pos, ctrl_wrapper in self.settings_workarounds[self.settings[0].cat_label].iteritems():
            ctrl_wrapper.setVisible(True)
            ctrl_wrapper.setEnabled(True)
        self.selected_cat_cache = self.settings[0].cat_label

        first_ctrl = self.button_dict[self.settings[0].cat_label][0]
        self.category_list.controlRight(first_ctrl.get_main_control())

    def build_settings_list(self, category, cat_settings):
        self.logger.info("Adding settings list items for category: %s" % category.cat_label)

        settings = []
        for setting_id, setting in cat_settings.iteritems():
            if setting.visible != "false":
                settings.append(setting)
        settings.sort(key=lambda x: x.priority, reverse=False)

        self.button_dict[category.cat_label] = []
        self.settings_workarounds[category.cat_label] = {}

        item_offset = 0
        for setting in settings:
            if setting.subsetting is True or setting.subsetting == 'true':
                label = "- %s" % setting.setting_label
            else:
                label = setting.setting_label

            label = xbmcgui.ControlLabel(
                400,
                152 + (44 * item_offset),
                1200,
                44,
                label=label,
                textColor='0xFF808080',
                font='Small'
            )

            self.addControl(label)
            label.setEnabled(False)
            label.setVisible(False)

            button = self.build_button_for_type(setting.type, item_offset, setting)

            button.setVisible(False)
            button.setEnabled(False)

            ctrl_wrapper = SettingGroup(self, label=label, control=button)

            pos = "%s:%s" % (category.cat_label, button.getY())
            previous_pos = "%s:%s" % (category.cat_label, button.getY() - 44)
            list_item = LinkedListItem(ctrl_wrapper)
            try:
                list_item.set_previous(self.settings_workarounds[category.cat_label][previous_pos])
            except KeyError:
                pass
            self.settings_workarounds[category.cat_label][pos] = list_item
            self.setting_id_group[setting.setting_id] = list_item
            self.button_dict[category.cat_label].append(ctrl_wrapper)

            item_offset += 1

        for setting in settings:
            if setting.enable:
                if category.cat_label not in self.needs_state_update:
                    self.needs_state_update[category.cat_label] = []

                for index_offset, target_value in self.parse_condition_to_dict(setting.enable).iteritems():
                    current_control = self.setting_id_group[setting.setting_id]

                    if int(index_offset) > 0:
                        target_control = current_control.get_x_next(index_offset)
                    else:
                        target_control = current_control.get_x_previous(index_offset)

                    self.logger.info(
                        "Setting is pointing to control: %s , offset: %s, target_control: %s" % (
                            setting.setting_id, index_offset, target_control))
                    current_control.append_enable_condition(target_control, target_value)
                    self.needs_state_update[category.cat_label].append(current_control)

            if setting.visible:
                if category.cat_label not in self.needs_state_update:
                    self.needs_state_update[category.cat_label] = []

                for index_offset, target_value in self.parse_condition_to_dict(setting.visible).iteritems():
                    current_control = self.setting_id_group[setting.setting_id]

                    if int(index_offset) > 0:
                        target_control = current_control.get_x_next(index_offset)
                    else:
                        target_control = current_control.get_x_previous(index_offset)

                    self.logger.info(
                        "Setting is pointing to control: %s , offset: %s, target_control: %s" % (
                            setting.setting_id, index_offset, target_control))
                    current_control.append_visible_condition(target_control, target_value)
                    self.needs_state_update[category.cat_label].append(current_control)

        for key, control in self.settings_workarounds[category.cat_label].iteritems():
            current_control = control

            previous_ctrl = current_control
            while previous_ctrl.has_previous():
                previous_ctrl = previous_ctrl.get_previous()
                if previous_ctrl.is_enabled():
                    break
            if previous_ctrl != current_control:
                current_control.controlUp(previous_ctrl.get_main_control())

            next_control = current_control
            while next_control.has_next():
                next_control = next_control.get_next()
                if next_control.is_enabled():
                    break
            if next_control != current_control:
                current_control.controlDown(next_control.get_main_control())

            current_control.controlLeft(self.category_list)

    def switch_settings_to_category(self, category, previous_category):
        if previous_category != '':
            for pos, ctrl_wrapper in self.settings_workarounds[previous_category].iteritems():
                ctrl_wrapper.setVisible(False)
                ctrl_wrapper.setEnabled(False)
        first = None
        for pos, ctrl_wrapper in self.settings_workarounds[category].iteritems():
            if not first:
                first = ctrl_wrapper
            if ctrl_wrapper.getY() < first.getY():
                first = ctrl_wrapper
            ctrl_wrapper.setVisible(True)
            ctrl_wrapper.setEnabled(True)

        self.category_list.controlRight(first.get_main_control())

    def build_button_for_type(self, control_type, item_offset, setting):
        value = setting.current_value
        if control_type == 'text':
            button = xbmcgui.ControlButton(
                700,
                152 + (44 * item_offset),
                1200,
                44,
                label=value,
                textColor='0xFF808080',
                focusedColor='0xFFE0B074',
                font='Small'
            )
            self.addControl(button)
            return button
        elif control_type == 'bool':
            focus_texture_on = os.path.join(xbmcaddon.Addon().getAddonInfo('path'),
                                            'resources/skins/Default/media/common/RadioOn.png')
            nofocus_texture_on = focus_texture_on
            focus_texture_off = os.path.join(xbmcaddon.Addon().getAddonInfo('path'),
                                             'resources/skins/Default/media/common/RadioOff.png')
            nofocus_texture_off = focus_texture_off

            button = xbmcgui.ControlRadioButton(
                700,
                152 + (44 * item_offset),
                200,
                44,
                label='',
                focusOnTexture=focus_texture_on,
                focusOffTexture=focus_texture_off,
                noFocusOnTexture=nofocus_texture_on,
                noFocusOffTexture=nofocus_texture_off
            )
            button.setRadioDimension(700, 152 + (44 * item_offset), 30, 30)
            self.addControl(button)

            if value == 'true':
                button.setSelected(True)

            return button
        elif control_type == 'labelenum':
            select_options = setting.values.split('|')

            base_path = xbmcaddon.Addon().getAddonInfo('path')
            btn_down_fo = os.path.join(base_path, 'resources/skins/Default/media/common/ArrowDownFO.png')
            btn_down_nf = os.path.join(base_path, 'resources/skins/Default/media/common/ArrowDownNF.png')
            btn_up_fo = os.path.join(base_path, 'resources/skins/Default/media/common/ArrowUpFO.png')
            btn_up_nf = os.path.join(base_path, 'resources/skins/Default/media/common/ArrowUpNF.png')

            btn_up = xbmcgui.ControlButton(
                1157,  # <--- 1280 - 100 (border) - 23 (element width, not necessary when using ALIGN_RIGHT)
                # int(152 + (44 * item_offset) - 8),
                152 + (44 * item_offset),
                23,
                44,
                label='',
                focusTexture=btn_up_fo,
                noFocusTexture=btn_up_nf
                # TODO: Try using image -> keep aspect ratio
            )

            btn_down = xbmcgui.ControlButton(
                1132,
                # int(152 + (44 * item_offset) - 8),
                152 + (44 * item_offset),
                23,
                44,
                label='',
                focusTexture=btn_down_fo,
                noFocusTexture=btn_down_nf
            )

            label = xbmcgui.ControlLabel(
                932,
                152 + (44 * item_offset),
                200,
                44,
                label='',
                textColor='0xFF808080',
                font='Small',
                alignment=1
            )
            # TODO: Use setting values list here (once it's been transformed from string to list)
            initial_index = 0
            for key, val in enumerate(select_options):
                if val == value:
                    initial_index = key

            rotary_select = RotarySelect(self, btn_up, btn_down, label, select_options, initial_index)
            self.forward_controls.append(rotary_select)
            return rotary_select
        elif control_type == 'slider':
            label = xbmcgui.ControlButton(
                650,
                152 + (44 * item_offset),
                200,
                44,
                label='',
                textColor='0xFF808080',
                font='Small'
            )

            range_items = setting.range.split(',')

            button = Slider(self, label, range(int(range_items[0]), int(range_items[2]), int(range_items[1])), value)
            self.forward_controls.append(button)
            return button

        else:
            button = xbmcgui.ControlButton(
                700,
                152 + (44 * item_offset),
                1200,
                44,
                label=value,
                textColor='0xFF808080',
                focusedColor='0xFFE0B074',
                font='Small'
            )
            self.addControl(button)
            return button

    def parse_condition_to_dict(self, condition_string):
        return {condition.strip()[3:-1].split(',')[0]: condition.strip()[3:-1].split(',')[1] for condition in
                condition_string.split("+")}

    def onAction(self, action):
        if action == xbmcgui.ACTION_NAV_BACK:
            self.close()

        selected_category = self.category_list.getSelectedItem()
        selected_category_label = selected_category.getLabel()
        self.logger.info("Currently Selected Category: %s" % selected_category_label)

        if selected_category_label != self.selected_cat_cache:
            previous_cat = self.selected_cat_cache
            self.logger.info("Category Changed: %s -> %s" % (previous_cat, selected_category_label))
            self.selected_cat_cache = selected_category_label
            self.switch_settings_to_category(selected_category_label, previous_cat)

        focus = self.getFocus()

        pos = "%s:%s" % (selected_category_label, focus.getY())

        if pos in self.settings_workarounds[selected_category_label] and focus != self.category_list:
            current_control = self.settings_workarounds[selected_category_label].get(pos)

            previously_selected_control = None
            if action == xbmcgui.ACTION_MOVE_DOWN:
                previous_control = current_control
                while previous_control.has_previous():
                    previous_control = previous_control.get_previous()
                    if previous_control.is_enabled():
                        previously_selected_control = previous_control
                        break

            if action == xbmcgui.ACTION_MOVE_UP:
                next_control = current_control
                while next_control.has_next():
                    next_control = next_control.get_next()
                    if next_control.is_enabled():
                        previously_selected_control = next_control
                        break

            if previously_selected_control:
                if previously_selected_control.getLabel()[1:6] == 'COLOR':
                    previously_selected_control.setLabel(
                        label=previously_selected_control.getLabel()[16:-8],
                        font='Small',
                    )

            if current_control.getLabel()[1:6] != 'COLOR':
                current_control.setLabel(
                    label='[COLOR FFE0B074]' + current_control.getLabel() + '[/COLOR]',
                    font='Small'
                )

        elif action == xbmcgui.ACTION_MOVE_LEFT:
            for key, wa_btn in self.settings_workarounds[selected_category_label].iteritems():
                self.logger.info("Changing Color for Label @ %s" % wa_btn)
                original_label = wa_btn.getLabel()
                if original_label[1:6] == 'COLOR':
                    original_label = original_label[16:-8]
                wa_btn.setLabel(
                    label=original_label,
                    font='Small'
                )

        # TODO: Only forward to controls of current category
        for control in self.forward_controls:
            control.forward_input(action.getId())

        # Use callbacks for this???
        if action == xbmcgui.ACTION_SELECT_ITEM and selected_category_label in self.needs_state_update:
            for control in self.needs_state_update[selected_category_label]:
                control.update_state()

        if action == xbmcgui.ACTION_SELECT_ITEM and focus == self.ok_btn:
            for setting_id, setting_ctrl_group in self.setting_id_group.iteritems():
                for category in self.settings:
                    if setting_id in category.settings:
                        _setting = category.settings[setting_id]
                        new_setting_value = setting_ctrl_group.get_value()
                        _setting.current_value = new_setting_value

            self.controller.save(self.settings)
            self.close()

        if action == xbmcgui.ACTION_SELECT_ITEM and focus == self.cancel_btn:
            self.close()
